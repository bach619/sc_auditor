"""GitHistoryAnalyzer — analyzes git history for vulnerability signals."""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("vyper.orchestrator.git_analysis")

# ── Patterns ────────────────────────────────────────────────────

_SECURITY_KEYWORDS: list[str] = [
    "fix", "security", "bug", "vuln", "exploit", "reentrancy",
    "overflow", "underflow", "access control", "race condition",
    "cve", "patch", "hotfix", "critical", "dos", "dos",
    "approve", "phishing", "sandwich", "flash loan",
]

_SECURITY_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in _SECURITY_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

_BUG_RE = re.compile(r"\b(bug|fix|patch|hotfix|fixup|workaround)\b", re.IGNORECASE)


# ── Data types ──────────────────────────────────────────────────

@dataclass
class CommitInfo:
    hash: str
    author: str
    date: datetime
    message: str
    files_changed: list[str]
    additions: int
    deletions: int
    is_security_relevant: bool = False

    @property
    def is_recent(self, days: int = 30) -> bool:
        return (datetime.now() - self.date).days <= days


@dataclass
class FileChurn:
    filepath: str
    commit_count: int
    total_additions: int
    total_deletions: int
    security_commits: int = 0
    contributors: set[str] = field(default_factory=set)

    @property
    def churn_score(self) -> float:
        """Normalised churn score 0–1."""
        return min(1.0, (self.total_additions + self.total_deletions) / 10_000)


@dataclass
class RepoAnalysis:
    repo_url: str
    branch: str = "main"
    total_commits: int = 0
    total_contributors: int = 0
    security_commits: int = 0
    high_churn_files: list[FileChurn] = field(default_factory=list)
    recent_activity_score: float = 0.0  # 0–1
    bug_density: float = 0.0  # bug-keyword commits / total
    analysis_date: datetime = field(default_factory=datetime.now)
    errors: list[str] = field(default_factory=list)


# ── Analyzer ────────────────────────────────────────────────────

class GitHistoryAnalyzer:
    """Clone / pull a repo and analyze its git history for vulnerability signals."""

    REPO_BASE_DIR = Path("/tmp/vyper_repos")

    def __init__(self, repo_base_dir: Path | None = None) -> None:
        self._base_dir = repo_base_dir or self.REPO_BASE_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)

    # ── Repo management ─────────────────────────────────────────

    def _repo_name(self, repo_url: str) -> str:
        """Extract a safe directory name from a git URL."""
        name = repo_url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        # Sanitize
        name = re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
        return name

    def _repo_path(self, repo_url: str) -> Path:
        return self._base_dir / self._repo_name(repo_url)

    def clone_or_pull(self, repo_url: str) -> Path:
        """Clone a repo, or pull if already cloned. Returns the repo path."""
        import git  # GitPython — shipped separately

        repo_path = self._repo_path(repo_url)
        if repo_path.exists():
            logger.info("Pulling existing repo %s", repo_url)
            repo = git.Repo(repo_path)
            origin = repo.remotes.origin
            origin.pull()
        else:
            logger.info("Cloning repo %s into %s", repo_url, repo_path)
            repo = git.Repo.clone_from(repo_url, repo_path)
        return repo_path

    # ── Analysis ─────────────────────────────────────────────────

    def analyze_history(self, repo_path: Path, branch: str = "main") -> RepoAnalysis:
        """Run full history analysis on a cloned repo."""
        import git

        try:
            repo = git.Repo(repo_path)
        except git.InvalidGitRepositoryError:
            return RepoAnalysis(
                repo_url=str(repo_path),
                errors=["Invalid git repository"],
            )

        analysis = RepoAnalysis(repo_url=str(repo_path), branch=branch)

        try:
            commits = list(repo.iter_commits(branch))
        except git.GitCommandError:
            commits = list(repo.iter_commits())

        analysis.total_commits = len(commits)
        file_churn_map: dict[str, FileChurn] = defaultdict(
            lambda: FileChurn(filepath="")
        )
        contributors: set[str] = set()
        security_count = 0
        bug_commit_count = 0

        for commit in commits:
            ci = CommitInfo(
                hash=commit.hexsha,
                author=commit.author.name or commit.author.email or "unknown",
                date=datetime.fromtimestamp(commit.committed_date),
                message=commit.message.strip(),
                files_changed=[],
                additions=commit.stats.total.get("insertions", 0),
                deletions=commit.stats.total.get("deletions", 0),
                is_security_relevant=bool(_SECURITY_RE.search(commit.message)),
            )
            contributors.add(ci.author)

            # File-level tracking
            if commit.parents:
                try:
                    for filepath, stats in commit.stats.files.items():
                        if filepath not in file_churn_map:
                            file_churn_map[filepath] = FileChurn(filepath=filepath)
                        fc = file_churn_map[filepath]
                        fc.commit_count += 1
                        fc.total_additions += stats.get("insertions", 0)
                        fc.total_deletions += stats.get("deletions", 0)
                        fc.contributors.add(ci.author)
                        if ci.is_security_relevant:
                            fc.security_commits += 1
                except Exception:
                    pass

            if ci.is_security_relevant:
                security_count += 1
            if _BUG_RE.search(commit.message):
                bug_commit_count += 1

        # Populate analysis
        analysis.total_contributors = len(contributors)
        analysis.security_commits = security_count
        analysis.bug_density = (
            bug_commit_count / analysis.total_commits if analysis.total_commits > 0 else 0.0
        )

        # High-churn files (top 20 by commit count)
        sorted_files = sorted(
            file_churn_map.values(),
            key=lambda f: f.commit_count,
            reverse=True,
        )
        analysis.high_churn_files = sorted_files[:20]

        # Recent activity: proportion of commits in last 30 days
        if commits:
            recent_cutoff = datetime.now().timestamp() - 30 * 86400
            recent_count = sum(
                1 for c in commits if c.committed_date >= recent_cutoff
            )
            analysis.recent_activity_score = recent_count / len(commits)

        return analysis

    def get_commit_metrics(self, repo_path: Path) -> dict[str, object]:
        """Quick summary stats without full analysis."""
        import git

        try:
            repo = git.Repo(repo_path)
        except git.InvalidGitRepositoryError:
            return {"error": "Invalid git repository"}

        try:
            commits = list(repo.iter_commits())
        except git.GitCommandError:
            commits = list(repo.iter_commits())

        if not commits:
            return {"total_commits": 0}

        dates = [datetime.fromtimestamp(c.committed_date) for c in commits]
        authors = Counter(c.author.name or c.author.email or "unknown" for c in commits)

        return {
            "total_commits": len(commits),
            "unique_authors": len(authors),
            "top_authors": authors.most_common(5),
            "first_commit": min(dates).isoformat(),
            "last_commit": max(dates).isoformat(),
            "timespan_days": (max(dates) - min(dates)).days,
            "security_keyword_commits": sum(
                1 for c in commits if _SECURITY_RE.search(c.message)
            ),
        }


__all__ = ["GitHistoryAnalyzer", "RepoAnalysis", "CommitInfo", "FileChurn"]
