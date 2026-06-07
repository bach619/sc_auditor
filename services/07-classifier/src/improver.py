"""Pattern learning and continuous improvement engine.

The PatternLearner extracts classification patterns from human feedback and
false-negative discoveries. These patterns are used by the Classifier to make
better decisions over time.

Pattern types (from the architecture spec §7.3):
- code_pattern: AST-based pattern matching against code snippets
- keyword_pattern: Title/description keyword matching
- severity_pattern: Severity-based classification rules
- tool_pattern: Per-tool confidence calibration

Learning data is shared between Classifier and Orchestrator via the
``/data/learning/`` volume (``vyper_learning`` Docker volume).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from src.models import (
    Classification,
    Feedback,
    FeedbackStatus,
    Finding,
    Pattern,
    PatternType,
)

log = structlog.get_logger()

# ── Constants ────────────────────────────────────────────────────────────

CLASSIFIER_DATA_DIR = Path("/data/classifier")
LEARNING_DATA_DIR = Path("/data/learning")

PATTERNS_FILE = CLASSIFIER_DATA_DIR / "patterns.json"
FINDINGS_FILE = CLASSIFIER_DATA_DIR / "findings.json"
FN_FILE = LEARNING_DATA_DIR / "false_negatives.json"
FP_FILE = LEARNING_DATA_DIR / "false_positives.json"
FEEDBACK_FILE = LEARNING_DATA_DIR / "feedback.json"

# Minimum effectiveness score for a pattern to be automatically activated
PATTERN_ACTIVATION_THRESHOLD: float = 0.6

# Number of correct matches before a pattern is considered "proven"
PATTERN_PROVEN_MATCHES: int = 5


# ── Helpers ──────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_json(path: Path, default: Any = None) -> Any:
    """Load JSON from a file, returning default if missing or corrupt."""
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("json_load_error", path=str(path), error=str(exc))
    return default if default is not None else {}


def _save_json(path: Path, data: Any) -> bool:
    """Save JSON atomically to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)
        return True
    except OSError as exc:
        log.error("json_save_error", path=str(path), error=str(exc))
        if tmp.exists():
            tmp.unlink()
        return False


# ── PatternLearner ───────────────────────────────────────────────────────


class PatternLearner:
    """Learns classification patterns from human feedback and FN discoveries.

    The learner maintains a pattern database and provides pattern matching
    capabilities to the Classifier. It continuously improves pattern
    effectiveness scores based on real-world usage.
    """

    def __init__(self) -> None:
        self._patterns: dict[str, dict[str, Any]] = _load_json(PATTERNS_FILE, {})
        self._feedback: list[dict[str, Any]] = _load_json(FEEDBACK_FILE, [])
        self._fn_records: list[dict[str, Any]] = _load_json(FN_FILE, [])
        self._fp_records: list[dict[str, Any]] = _load_json(FP_FILE, [])
        log.info(
            "pattern_learner_initialized",
            patterns=len(self._patterns),
            feedback=len(self._feedback),
            fn_records=len(self._fn_records),
        )

    # ── Pattern Matching ─────────────────────────────────────────────────

    def match_pattern(self, finding: Finding) -> Pattern | None:
        """Check if a finding matches any known classification pattern.

        Iterates over active patterns sorted by effectiveness score and
        returns the first strong match.

        Args:
            finding: The finding to check against known patterns.

        Returns:
            The matching Pattern with the highest effectiveness score,
            or None if no pattern matches.
        """
        best_match: Pattern | None = None
        best_score: float = 0.0

        for pdata in self._patterns.values():
            if not pdata.get("is_active", True):
                continue

            pattern = Pattern(**pdata)
            score = self._score_match(finding, pattern)

            if score > 0.0 and score > best_score:
                best_score = score
                best_match = pattern

        # Only return if the match exceeds the activation threshold
        if best_match is not None and best_score >= PATTERN_ACTIVATION_THRESHOLD:
            return best_match
        return None

    def _score_match(self, finding: Finding, pattern: Pattern) -> float:
        """Compute a match score between a finding and a pattern (0.0–1.0).

        Different pattern types use different matching strategies:
        - code_pattern: Checks if pattern rules' keywords appear in code_snippet
        - keyword_pattern: Checks title/description against pattern keywords
        - severity_pattern: Matches on severity level
        - tool_pattern: Matches on tool name and confidence
        """
        rules = pattern.rules
        if not rules:
            return 0.0

        pattern_type = pattern.pattern_type

        if pattern_type == PatternType.KEYWORD_PATTERN:
            keywords = rules.get("keywords", [])
            if not keywords:
                return 0.0
            haystack = f"{finding.title} {finding.description or ''}".lower()
            matches = sum(1 for kw in keywords if kw.lower() in haystack)
            return matches / len(keywords) if matches > 0 else 0.0

        elif pattern_type == PatternType.CODE_PATTERN:
            code_patterns = rules.get("code_patterns", [])
            if not code_patterns or not finding.code_snippet:
                return 0.0
            snippet = finding.code_snippet.lower()
            matches = sum(1 for cp in code_patterns if cp.lower() in snippet)
            return matches / len(code_patterns) if matches > 0 else 0.0

        elif pattern_type == PatternType.SEVERITY_PATTERN:
            target_severity = rules.get("severity")
            if target_severity and finding.severity:
                if finding.severity.value == target_severity.lower():
                    return rules.get("confidence_boost", 0.7)
            return 0.0

        elif pattern_type == PatternType.TOOL_PATTERN:
            tool_name = rules.get("tool_name", "").lower()
            if (
                tool_name
                and finding.tool
                and finding.tool.name.lower() == tool_name
            ):
                return rules.get("confidence_boost", 0.6)
            return 0.0

        return 0.0

    # ── Learning from Feedback ───────────────────────────────────────────

    def learn_from_feedback(self, feedback: Feedback) -> Pattern | None:
        """Extract and register a classification pattern from human feedback.

        Analyzes the feedback to determine if a reusable pattern can be
        extracted. Patterns are only created if the feedback provides
        enough information (notes, original finding context).

        Args:
            feedback: The human feedback to learn from.

        Returns:
            The generated Pattern if one was created, None otherwise.
        """
        # Only learn from finalized feedback
        if feedback.status != FeedbackStatus.FINALIZED:
            log.info(
                "feedback_not_finalized_skipping_learning",
                feedback_id=feedback.feedback_id,
                status=feedback.status.value,
            )
            return None

        # Store the feedback
        fdata = feedback.model_dump()
        self._feedback.append(fdata)
        _save_json(FEEDBACK_FILE, self._feedback)

        # Determine if this is an FN or FP correction (most valuable for learning)
        is_fn = (
            feedback.correct_classification == Classification.TRUE_POSITIVE
            and feedback.original_classification in (
                Classification.FALSE_NEGATIVE, Classification.UNKNOWN
            )
        )
        is_fp = (
            feedback.correct_classification == Classification.FALSE_POSITIVE
            and feedback.original_classification == Classification.TRUE_POSITIVE
        )

        if is_fn:
            fn_record = {
                "finding_id": feedback.finding_id,
                "feedback_id": feedback.feedback_id,
                "original_classification": (
                    feedback.original_classification.value
                    if feedback.original_classification
                    else "unknown"
                ),
                "notes": feedback.notes,
                "discovered_at": _now_iso(),
            }
            self._fn_records.append(fn_record)
            _save_json(FN_FILE, self._fn_records)
            log.info("fn_discovered_learning", finding_id=feedback.finding_id)

            # Generate a pattern from this FN discovery
            pattern = self._generate_pattern_from_fn(fn_record)
            if pattern:
                self.add_pattern(pattern)
                return pattern

        elif is_fp:
            fp_record = {
                "finding_id": feedback.finding_id,
                "feedback_id": feedback.feedback_id,
                "notes": feedback.notes,
                "discovered_at": _now_iso(),
            }
            self._fp_records.append(fp_record)
            _save_json(FP_FILE, self._fp_records)
            log.info("fp_discovered_learning", finding_id=feedback.finding_id)

            pattern = self._generate_pattern_from_fp(fp_record)
            if pattern:
                self.add_pattern(pattern)
                return pattern

        else:
            log.debug(
                "feedback_recorded_no_pattern",
                feedback_id=feedback.feedback_id,
                classification=feedback.correct_classification.value,
            )

        # Even without a new pattern, update effectiveness of existing patterns
        self._update_pattern_effectiveness(feedback)
        return None

    def learn_from_fn(self, fn_record: dict[str, Any]) -> Pattern | None:
        """Learn from a missed bug (false negative) record.

        False negatives are the most important learning signals — they
        represent bugs that the entire pipeline missed.

        Args:
            fn_record: Record of a false negative discovery. Should include
                       finding_id, notes, and optionally code_snippet.

        Returns:
            A new Pattern if one could be generated, None otherwise.
        """
        self._fn_records.append(fn_record)
        _save_json(FN_FILE, self._fn_records)
        log.info("fn_learning_triggered", finding_id=fn_record.get("finding_id"))

        pattern = self._generate_pattern_from_fn(fn_record)
        if pattern:
            self.add_pattern(pattern)
        return pattern

    # ── Learning from Exploit Feedback ───────────────────────────────────

    def learn_from_exploit(
        self,
        finding_id: str,
        exploit_successful: bool,
        classification: Classification,
    ) -> Pattern | None:
        """Learn from automated exploit feedback.

        Unlike human feedback (which goes through INITIAL→REVIEWED→FINALIZED),
        exploit feedback is AUTOMATICALLY used because it's objective truth.

        Args:
            finding_id: The finding identifier.
            exploit_successful: Whether exploit worked.
            classification: The resulting classification.

        Returns:
            The created/updated pattern, or None.
        """
        # Load finding data to extract pattern attributes
        finding_data = None
        try:
            if FINDINGS_FILE.exists():
                with open(FINDINGS_FILE) as f:
                    all_findings = json.load(f)
                    finding_data = all_findings.get(finding_id)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("exploit_learning.load_error", error=str(exc))

        if not finding_data:
            log.warning("exploit_learning.no_finding_data", finding_id=finding_id)
            return None

        title = finding_data.get("title", "")
        tool_name = ""
        tool_info = finding_data.get("tool")
        if isinstance(tool_info, dict):
            tool_name = tool_info.get("name", "")
        severity = finding_data.get("severity", "")

        # Create a pattern key from finding attributes
        pattern_key = f"exploit_{tool_name}_{severity}_{title[:50]}"

        if exploit_successful and classification == Classification.TRUE_POSITIVE:
            log.info(
                "exploit_learning.tp_confirmed",
                finding_id=finding_id,
                pattern_key=pattern_key,
            )
            return self._register_or_update_pattern(
                pattern_key=pattern_key,
                classification=Classification.TRUE_POSITIVE,
                weight_increase=0.15,
            )

        elif not exploit_successful:
            log.info(
                "exploit_learning.fp_suspected",
                finding_id=finding_id,
                pattern_key=pattern_key,
            )
            return self._register_or_update_pattern(
                pattern_key=pattern_key,
                classification=Classification.FALSE_POSITIVE,
                weight_increase=-0.1,
            )

        return None

    def _register_or_update_pattern(
        self,
        pattern_key: str,
        classification: Classification,
        weight_increase: float,
    ) -> Pattern | None:
        """Register a new pattern or update existing one's effectiveness score.

        Args:
            pattern_key: Unique key derived from finding attributes.
            classification: The classification this pattern represents.
            weight_increase: Amount to adjust effectiveness score.

        Returns:
            The created or updated Pattern, or None.
        """
        now_iso = datetime.now(UTC).isoformat()

        # Check if pattern already exists (by key in dict or by name)
        for pdata in self._patterns.values():
            pattern = Pattern(**pdata)
            if pattern.name == pattern_key or pattern.pattern_id == pattern_key:
                old_score = pattern.effectiveness_score
                pattern.effectiveness_score = max(
                    0.0, min(1.0, pattern.effectiveness_score + weight_increase)
                )
                pattern.match_count += 1
                if weight_increase > 0:
                    pattern.correct_count += 1
                pattern.updated_at = now_iso
                self._patterns[pattern.pattern_id] = pattern.model_dump()
                _save_json(PATTERNS_FILE, self._patterns)
                log.info(
                    "pattern_updated_from_exploit",
                    pattern_id=pattern.pattern_id,
                    old_score=old_score,
                    new_score=pattern.effectiveness_score,
                )
                return pattern

        # Create new pattern
        pattern = Pattern(
            pattern_id=pattern_key,
            name=pattern_key,
            pattern_type=PatternType.CODE_PATTERN,
            classification=classification,
            description=f"Auto-learned from exploit feedback: {classification.value}",
            effectiveness_score=0.5 + max(0, weight_increase),
            match_count=1,
            correct_count=1 if weight_increase > 0 else 0,
            is_active=True,
        )
        self._patterns[pattern.pattern_id] = pattern.model_dump()
        _save_json(PATTERNS_FILE, self._patterns)
        log.info(
            "pattern_created_from_exploit",
            pattern_id=pattern.pattern_id,
            classification=classification.value,
        )
        return pattern

    # ── Pattern Management ───────────────────────────────────────────────

    def add_pattern(self, pattern: Pattern) -> Pattern:
        """Add a new pattern to the database.

        If a pattern with the same name already exists, the existing pattern
        is updated with the new rules and a version bump.

        Args:
            pattern: The pattern to add or update.

        Returns:
            The pattern as stored (may have updated fields).
        """
        now = _now_iso()
        existing = self._patterns.get(pattern.pattern_id)

        if existing:
            existing["rules"] = pattern.model_dump().get("rules", {})
            existing["description"] = pattern.description
            existing["updated_at"] = now
            log.info("pattern_updated", pattern_id=pattern.pattern_id)
        else:
            self._patterns[pattern.pattern_id] = pattern.model_dump()
            log.info("pattern_created", pattern_id=pattern.pattern_id)

        _save_json(PATTERNS_FILE, self._patterns)
        return Pattern(**self._patterns[pattern.pattern_id])

    def get_patterns(self) -> list[dict[str, Any]]:
        """Return all patterns with their effectiveness scores.

        Returns:
            List of pattern dictionaries sorted by effectiveness (descending).
        """
        patterns = [Pattern(**p) for p in self._patterns.values()]
        patterns.sort(key=lambda p: p.effectiveness_score, reverse=True)

        return [
            {
                "pattern_id": p.pattern_id,
                "name": p.name,
                "pattern_type": p.pattern_type.value,
                "classification": p.classification.value,
                "description": p.description,
                "effectiveness_score": round(p.effectiveness_score, 4),
                "match_count": p.match_count,
                "correct_count": p.correct_count,
                "accuracy": round(
                    p.correct_count / p.match_count if p.match_count > 0 else 0.0,
                    4,
                ),
                "is_active": p.is_active,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            for p in patterns
        ]

    def deactivate_pattern(self, pattern_id: str) -> bool:
        """Deactivate a pattern (soft-delete).

        Args:
            pattern_id: ID of the pattern to deactivate.

        Returns:
            True if the pattern was found and deactivated.
        """
        if pattern_id in self._patterns:
            self._patterns[pattern_id]["is_active"] = False
            self._patterns[pattern_id]["updated_at"] = _now_iso()
            _save_json(PATTERNS_FILE, self._patterns)
            log.info("pattern_deactivated", pattern_id=pattern_id)
            return True
        return False

    # ── Pattern Generation ───────────────────────────────────────────────

    def _generate_pattern_from_fn(
        self, fn_record: dict[str, Any]
    ) -> Pattern | None:
        """Generate a pattern from a false negative discovery.

        Creates a keyword-based pattern using the notes and finding context
        to help detect similar bugs in the future.
        """
        notes = fn_record.get("notes", "")
        finding_id = fn_record.get("finding_id", "")

        if not notes and not finding_id:
            return None

        pattern_id = f"fn-pattern-{uuid.uuid4().hex[:12]}"
        keywords = self._extract_keywords(notes)

        # Attempt to look up the original finding for more context
        code_snippet = fn_record.get("code_snippet", "")

        rules: dict[str, Any] = {
            "keywords": keywords if keywords else [notes[:50]],
        }

        pattern_type = PatternType.KEYWORD_PATTERN

        if code_snippet:
            # If we have code context, prefer code pattern matching
            rules["code_patterns"] = self._extract_code_patterns(code_snippet)

        if code_snippet and rules.get("code_patterns"):
            pattern_type = PatternType.CODE_PATTERN

        return Pattern(
            pattern_id=pattern_id,
            name=f"FN Pattern: {self._summarize(notes, 60)}",
            pattern_type=pattern_type,
            classification=Classification.TRUE_POSITIVE,
            description=(
                f"Learned from false negative (finding: {finding_id}). "
                f"Notes: {notes[:200]}"
            ),
            rules=rules,
            effectiveness_score=0.5,  # Start at 0.5, will be tuned by usage
            source_feedback_id=fn_record.get("feedback_id"),
            is_active=True,
        )

    def _generate_pattern_from_fp(
        self, fp_record: dict[str, Any]
    ) -> Pattern | None:
        """Generate a pattern from a false positive correction.

        Creates a pattern that helps identify similar false positives
        in the future, reducing noise.
        """
        notes = fp_record.get("notes", "")
        finding_id = fp_record.get("finding_id", "")

        if not notes and not finding_id:
            return None

        pattern_id = f"fp-pattern-{uuid.uuid4().hex[:12]}"
        keywords = self._extract_keywords(notes)
        code_snippet = fp_record.get("code_snippet", "")

        rules: dict[str, Any] = {
            "keywords": keywords if keywords else [notes[:50]],
        }

        if code_snippet:
            rules["code_patterns"] = self._extract_code_patterns(code_snippet)

        return Pattern(
            pattern_id=pattern_id,
            name=f"FP Pattern: {self._summarize(notes, 60)}",
            pattern_type=PatternType.KEYWORD_PATTERN,
            classification=Classification.FALSE_POSITIVE,
            description=(
                f"Learned from false positive correction (finding: {finding_id}). "
                f"Notes: {notes[:200]}"
            ),
            rules=rules,
            effectiveness_score=0.5,
            source_feedback_id=fp_record.get("feedback_id"),
            is_active=True,
        )

    # ── Utility ──────────────────────────────────────────────────────────

    def _update_pattern_effectiveness(self, feedback: Feedback) -> None:
        """Update effectiveness scores for patterns related to this feedback.

        Iterates over patterns that match the feedback's original classification
        and adjusts their effectiveness scores based on whether the feedback
        confirms or contradicts them.
        """
        for pdata in self._patterns.values():
            pattern = Pattern(**pdata)

            # Check if this pattern would have matched this feedback's finding
            feedback_class = feedback.correct_classification
            pattern_class = pattern.classification

            # Pattern was correct if its classification matches human feedback
            was_correct = (feedback_class == pattern_class)
            pattern.match_count += 1
            if was_correct:
                pattern.correct_count += 1

            # Update effectiveness: ratio of correct to total matches
            pattern.effectiveness_score = (
                pattern.correct_count / pattern.match_count
                if pattern.match_count > 0
                else 0.5
            )

            # Auto-deactivate if consistently wrong
            if (
                pattern.match_count >= PATTERN_PROVEN_MATCHES
                and pattern.effectiveness_score < 0.3
            ):
                pattern.is_active = False
                log.warning(
                    "pattern_auto_deactivated_low_effectiveness",
                    pattern_id=pattern.pattern_id,
                    score=pattern.effectiveness_score,
                )

            pattern.updated_at = _now_iso()
            self._patterns[pattern.pattern_id] = pattern.model_dump()

        _save_json(PATTERNS_FILE, self._patterns)

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Extract meaningful keywords from a text description.

        Splits on whitespace and punctuation, filters out short/common words,
        and returns unique lowercase keywords.
        """
        stop_words: frozenset[str] = frozenset({
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "out", "off", "over", "under", "again",
            "further", "then", "once", "this", "that", "these", "those",
            "and", "but", "or", "not", "no", "nor", "so", "yet", "both",
            "either", "neither", "each", "every", "all", "any", "few",
            "more", "most", "other", "some", "such", "only", "own",
            "same", "than", "too", "very", "just", "because", "if",
            "about", "up", "down", "it", "its", "it's",
        })

        raw = text.lower().replace(",", " ").replace(".", " ").replace("\n", " ")
        # Extract potential compound terms (e.g., "reentrancy guard", "access control")
        words = raw.split()
        keywords: list[str] = []
        for i, word in enumerate(words):
            word = word.strip("():;\"'[]{}")
            if len(word) >= 4 and word not in stop_words:
                keywords.append(word)
            # Bigrams for compound terms
            if i > 0:
                bigram = f"{words[i - 1]} {word}".strip("():;\"'[]{}")
                if len(bigram) >= 6:
                    keywords.append(bigram)
        return list(set(keywords))[:20]  # Max 20 unique keywords

    @staticmethod
    def _extract_code_patterns(code_snippet: str) -> list[str]:
        """Extract code patterns from a code snippet.

        Extracts function names, modifiers, and key language constructs
        that can be used for AST-like pattern matching.
        """
        patterns: list[str] = []
        lines = code_snippet.split("\n")
        import re

        for line in lines:
            line = line.strip()
            # Function/method definitions
            func_match = re.search(
                r"(?:function|def|fn|fun)\s+(\w+)", line, re.IGNORECASE
            )
            if func_match:
                patterns.append(func_match.group(1))
            # Modifier patterns in Solidity
            mod_match = re.search(r"modifier\s+(\w+)", line, re.IGNORECASE)
            if mod_match:
                patterns.append(mod_match.group(1))
            # Key language keywords (Solidity/Vyper specific)
            for kw in [
                "require", "assert", "revert", "call", "delegatecall",
                "send", "transfer", "selfdestruct", "suicide",
            ]:
                if kw in line.lower() and kw not in patterns:
                    patterns.append(kw)
            # External/public function calls (potential reentrancy)
            if ".call" in line.lower() and "call" not in patterns:
                patterns.append("call")

        return list(set(patterns))[:15]  # Max 15 patterns

    @staticmethod
    def _summarize(text: str, max_len: int = 80) -> str:
        """Truncate text for use as a pattern name."""
        clean = text.replace("\n", " ").strip()
        if len(clean) <= max_len:
            return clean
        return clean[: max_len - 3] + "..."
