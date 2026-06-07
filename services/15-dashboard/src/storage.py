"""Case Storage Engine — YAML file-based storage for Case Management System.

Agenda 05: Each Bug Is Cases
═══════════════════════════════════════════════════════════════

Storage architecture (100% local, no database):
  ~/.sc_auditor/
    ├── cases/
    │   ├── CASE-001/
    │   │   ├── meta.yaml      # Case metadata (Pydantic model → YAML)
    │   │   ├── report.md       # Generated Markdown report
    │   │   ├── report.pdf      # Generated PDF report (via weasyprint)
    │   │   ├── poc/            # PoC exploit files
    │   │   └── evidence/       # Screenshots, logs
    │   ├── CASE-002/
    │   └── ...
    ├── learning/
    │   ├── patterns.yaml
    │   ├── knowledge.json
    │   └── index.json
    ├── config.yaml
    └── app.log

Case ID format: CASE-XXX (zero-padded, e.g. CASE-001, CASE-042)
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import structlog
import yaml

from src.confidence import (
    get_pattern_weight,
    hitung_confidence_label,
    load_patterns,
    update_pattern_learning,
)
from src.models import (
    CONFIDENCE_LABEL_ORDER,
    Case,
    CaseCreate,
    CaseStats,
    CaseStatus,
    ClosedReason,
    ScannerFinding,
)

logger = structlog.get_logger(service="case_storage")

# ── Constants ───────────────────────────────────────────────────

SC_AUDITOR_DIR = Path.home() / ".sc_auditor"
CASES_DIR = SC_AUDITOR_DIR / "cases"
LEARNING_DIR = SC_AUDITOR_DIR / "learning"
CONFIG_FILE = SC_AUDITOR_DIR / "config.yaml"
LOG_FILE = SC_AUDITOR_DIR / "app.log"

CASE_ID_PATTERN = re.compile(r"^CASE-(\d{3,})$")


# ── Initialization ──────────────────────────────────────────────

def ensure_dirs() -> None:
    """Create all required directories if they don't exist."""
    for d in [SC_AUDITOR_DIR, CASES_DIR, LEARNING_DIR, CASES_DIR / "learning"]:
        d.mkdir(parents=True, exist_ok=True)
    logger.info("Storage directories ensured", path=str(SC_AUDITOR_DIR))


# ── Case ID Generation ──────────────────────────────────────────

def _next_case_id() -> str:
    """Generate the next CASE-XXX ID based on existing cases."""
    max_num = 0
    if CASES_DIR.exists():
        for entry in CASES_DIR.iterdir():
            if entry.is_dir():
                m = CASE_ID_PATTERN.match(entry.name)
                if m:
                    num = int(m.group(1))
                    if num > max_num:
                        max_num = num
    return f"CASE-{max_num + 1:03d}"


def _validate_case_id(case_id: str) -> bool:
    """Validate that case_id matches CASE-XXX format (path traversal protection)."""
    return bool(CASE_ID_PATTERN.match(case_id))


def _case_dir(case_id: str) -> Path:
    """Get the directory path for a case. Validates case_id format."""
    if not _validate_case_id(case_id):
        raise ValueError(f"Invalid case_id format: {case_id}")
    return CASES_DIR / case_id


def _meta_path(case_id: str) -> Path:
    """Get the meta.yaml path for a case."""
    return _case_dir(case_id) / "meta.yaml"


def _report_md_path(case_id: str) -> Path:
    """Get the report.md path for a case."""
    return _case_dir(case_id) / "report.md"


def _report_pdf_path(case_id: str) -> Path:
    """Get the report.pdf path for a case."""
    return _case_dir(case_id) / "report.pdf"


def _poc_dir(case_id: str) -> Path:
    """Get the PoC directory for a case."""
    return _case_dir(case_id) / "poc"


def _evidence_dir(case_id: str) -> Path:
    """Get the evidence directory for a case."""
    return _case_dir(case_id) / "evidence"


# ── CRUD Operations ─────────────────────────────────────────────

def create_case(data: CaseCreate) -> Case:
    """Create a new case from scanner findings.

    Dedup: If an OPEN case already exists with the same contract + function +
    vulnerability class (detector), MERGE the new findings into the existing case
    instead of creating a new one (per Spec Section 2.4 Rule 2 & 2.5).
    """
    ensure_dirs()

    # ── Step 1: Dedup check — find matching open case ──────────
    existing = _find_matching_open_case(
        project=data.project,
        contract=data.contract,
        function=data.function,
        new_scanners=data.scanners,
    )
    if existing is not None:
        return _merge_into_existing(existing, data)

    # ── Step 2: No match — create new case ────────────────────
    case_id = _next_case_id()
    now = datetime.now(UTC).isoformat()

    # Calculate confidence label and factors
    scanner_count = len(data.scanners)

    patterns = load_patterns(LEARNING_DIR / "patterns.yaml")
    vuln_class = data.scanners[0].detector if data.scanners else "unknown"
    pattern_weight = get_pattern_weight(vuln_class, data.contract, data.function, patterns)

    confidence_label, confidence_factors = hitung_confidence_label(
        scanner_count=scanner_count,
        has_poc=bool(data.proof_of_concept),
        pattern_weight=pattern_weight,
        vuln_category=vuln_class,
    )

    label_to_conf = {"Critical": 0.95, "High": 0.80, "Medium": 0.60, "Low": 0.30}
    numeric_confidence = label_to_conf.get(confidence_label.value, 0.50)

    case = Case(
        case_id=case_id,
        status=CaseStatus.OPEN,
        project=data.project,
        scanners=data.scanners,
        confidence=numeric_confidence,
        confidence_label=confidence_label.value,
        confidence_factors=confidence_factors,
        scanner_count=scanner_count,
        severity=data.severity,
        title=data.title,
        contract=data.contract,
        function=data.function,
        line=data.line,
        description=data.description,
        recommendation=data.recommendation,
        proof_of_concept=data.proof_of_concept,
        platform=data.platform,
        notes=data.notes,
        created_at=now,
    )

    # Create case directory and write meta.yaml
    cdir = _case_dir(case_id)
    cdir.mkdir(parents=True, exist_ok=True)
    _poc_dir(case_id).mkdir(exist_ok=True)
    _evidence_dir(case_id).mkdir(exist_ok=True)

    _write_yaml(case)

    # Generate initial report
    _generate_report_md(case)

    logger.info("Case created", case_id=case_id, title=data.title, severity=data.severity)
    return case


# ── Dedup Logic (Spec Section 2.4 Rule 2 & 2.5) ────────────────

def _find_matching_open_case(
    project: str,
    contract: str,
    function: str,
    new_scanners: list[ScannerFinding],
) -> Case | None:
    """Find an existing OPEN case that matches the same bug.

    Matching criteria (Spec Section 2.5):
    1. Contract yang sama
    2. Function yang sama
    3. Vulnerability class (detector) yang sama
    """
    if not CASES_DIR.exists():
        return None

    # Extract vulnerability classes from new findings
    new_vuln_classes = {s.detector.lower() for s in new_scanners}

    for entry in sorted(CASES_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if not CASE_ID_PATTERN.match(entry.name):
            continue

        meta = entry / "meta.yaml"
        if not meta.exists():
            continue

        case = _read_yaml_from_path(entry.name, meta)
        if case is None:
            continue
        if case.status != CaseStatus.OPEN:
            continue
        if case.contract.lower() != contract.lower():
            continue
        if case.function.lower() != function.lower():
            continue

        # Check if any existing scanner covers the same vuln class
        existing_vuln_classes = {s.detector.lower() for s in case.scanners}
        if new_vuln_classes & existing_vuln_classes:
            logger.info(
                "Dedup match found",
                existing_case=case.case_id,
                contract=contract,
                function=function,
                matching_classes=list(new_vuln_classes & existing_vuln_classes),
            )
            return case

    return None


def _merge_into_existing(existing: Case, data: CaseCreate) -> Case:
    """Merge new scanner findings into an existing case.

    The following happen:
    - New scanners (not already present) are appended
    - Confidence is recalculated as the average of ALL scanner confidences
    - scanner_count is updated
    - Description/Recommendation updated if provided
    """
    existing_scanner_names = {(s.name, s.detector) for s in existing.scanners}

    # Add only scanner findings that aren't already in the case
    for new_s in data.scanners:
        key = (new_s.name, new_s.detector)
        if key not in existing_scanner_names:
            existing.scanners.append(new_s)
            existing_scanner_names.add(key)

    # Recalculate confidence label and factors
    scanner_count = len(existing.scanners)
    patterns = load_patterns(LEARNING_DIR / "patterns.yaml")
    vuln_class = existing.scanners[0].detector if existing.scanners else "unknown"
    pattern_weight = get_pattern_weight(vuln_class, existing.contract, existing.function, patterns)

    confidence_label, confidence_factors = hitung_confidence_label(
        scanner_count=scanner_count,
        has_poc=bool(existing.proof_of_concept),
        pattern_weight=pattern_weight,
        vuln_category=vuln_class,
    )

    label_to_conf = {"Critical": 0.95, "High": 0.80, "Medium": 0.60, "Low": 0.30}
    existing.confidence = label_to_conf.get(confidence_label.value, 0.50)
    existing.confidence_label = confidence_label.value
    existing.confidence_factors = confidence_factors
    existing.scanner_count = scanner_count

    # Update metadata if new info is better
    if data.title and existing.title != data.title:
        # Keep the more descriptive title (longer wins)
        if len(data.title) > len(existing.title):
            existing.title = data.title
    if data.description and len(data.description) > len(existing.description):
        existing.description = data.description
    if data.recommendation:
        existing.recommendation = data.recommendation
    if data.severity:
        # Upgrade severity if new finding is more severe
        sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
        existing_sev_idx = sev_order.get(existing.severity, 99)
        new_sev_idx = sev_order.get(data.severity, 99)
        if new_sev_idx < existing_sev_idx:
            existing.severity = data.severity

    _write_yaml(existing)
    _generate_report_md(existing)

    logger.info(
        "Case merged (dedup)",
        case_id=existing.case_id,
        new_confidence=existing.confidence,
        scanner_count=existing.scanner_count,
    )
    return existing


def get_case(case_id: str) -> Case | None:
    """Get a case by ID. Returns None if not found or invalid case_id."""
    if not _validate_case_id(case_id):
        return None
    meta = _meta_path(case_id)
    if not meta.exists():
        return None
    return _read_yaml(case_id)


def list_cases(status: str | None = None, search: str | None = None,
               severity: str | None = None,
               confidence: str | None = None, sort: str = "created_at",
               order: str = "desc", limit: int = 100, offset: int = 0) -> list[Case]:
    """List cases with optional filtering, sorting, and pagination."""
    ensure_dirs()
    cases: list[Case] = []

    if not CASES_DIR.exists():
        return cases

    for entry in sorted(CASES_DIR.iterdir()):
        if entry.is_dir() and CASE_ID_PATTERN.match(entry.name):
            meta = entry / "meta.yaml"
            if meta.exists():
                case = _read_yaml_from_path(entry.name, meta)
                if case is None:
                    continue

                # Filter by status
                if status and case.status.value != status:
                    continue

                # Filter by severity
                if severity and case.severity.lower() != severity.lower():
                    continue

                # Filter by confidence label
                if confidence and case.confidence_label.lower() != confidence.lower():
                    continue

                # Search in title, contract, description
                if search:
                    q = search.lower()
                    if (q not in case.title.lower()
                            and q not in case.contract.lower()
                            and q not in case.description.lower()
                            and q not in case.case_id.lower()):
                        continue

                cases.append(case)

    # Sort
    reverse = order.lower() == "desc"
    if sort == "confidence":
        cases.sort(key=lambda c: CONFIDENCE_LABEL_ORDER.get(c.confidence_label, 99), reverse=not reverse)
    elif sort == "severity":
        sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
        cases.sort(key=lambda c: sev_order.get(c.severity, 99), reverse=reverse)
    elif sort == "title":
        cases.sort(key=lambda c: c.title.lower(), reverse=reverse)
    else:  # created_at
        cases.sort(key=lambda c: c.created_at, reverse=reverse)

    # Paginate
    return cases[offset:offset + limit]


def list_cases_with_total(
    status: str | None = None,
    search: str | None = None,
    severity: str | None = None,
    confidence: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Case], int]:
    """Like list_cases but also returns total count (single I/O pass)."""
    ensure_dirs()
    all_filtered: list[Case] = []

    if not CASES_DIR.exists():
        return [], 0

    for entry in sorted(CASES_DIR.iterdir()):
        if entry.is_dir() and CASE_ID_PATTERN.match(entry.name):
            meta = entry / "meta.yaml"
            if meta.exists():
                case = _read_yaml_from_path(entry.name, meta)
                if case is None:
                    continue

                if status and case.status.value != status:
                    continue
                if severity and case.severity.lower() != severity.lower():
                    continue
                if confidence and case.confidence_label.lower() != confidence.lower():
                    continue
                if search:
                    q = search.lower()
                    if (q not in case.title.lower()
                            and q not in case.contract.lower()
                            and q not in case.description.lower()
                            and q not in case.case_id.lower()):
                        continue

                all_filtered.append(case)

    total = len(all_filtered)

    # Sort
    reverse = order.lower() == "desc"
    if sort == "confidence":
        all_filtered.sort(key=lambda c: CONFIDENCE_LABEL_ORDER.get(c.confidence_label, 99), reverse=not reverse)
    elif sort == "severity":
        sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
        all_filtered.sort(key=lambda c: sev_order.get(c.severity, 99), reverse=reverse)
    elif sort == "title":
        all_filtered.sort(key=lambda c: c.title.lower(), reverse=reverse)
    elif sort == "closed_at":
        all_filtered.sort(key=lambda c: c.closed_at or "", reverse=reverse)
    else:
        all_filtered.sort(key=lambda c: c.created_at, reverse=reverse)

    return all_filtered[offset:offset + limit], total


def close_case(case_id: str, reason: ClosedReason, bounty: float | None = None,
               notes: str = "") -> Case | None:
    """Close a case. Returns None if case not found or already closed."""
    case = get_case(case_id)
    if case is None:
        return None
    if case.status == CaseStatus.CLOSED:
        return None  # No ghost reopen

    case.status = CaseStatus.CLOSED
    case.closed_at = datetime.now(UTC).isoformat()
    case.closed_reason = reason.value
    if bounty is not None:
        case.bounty_amount = bounty
    if notes:
        case.notes = (case.notes + "\n" + notes).strip()

    _write_yaml(case)

    # Regenerate reports so they include closure info
    _generate_report_md(case)
    _generate_report_pdf(case)

    # Update pattern learning
    try:
        vuln_class = case.scanners[0].detector if case.scanners else "unknown"
        update_pattern_learning(
            vuln_class=vuln_class,
            contract=case.contract,
            function=case.function,
            is_confirmed=(reason == ClosedReason.CONFIRMED),
            case_id=case.case_id,
            bounty=bounty,
        )
    except Exception as e:
        logger.error("Pattern learning update failed", case_id=case.case_id, error=str(e))

    # Archive to learning
    _archive_to_learning(case)

    logger.info("Case closed", case_id=case_id, reason=reason.value, bounty=bounty)
    return case


def get_case_stats() -> CaseStats:
    """Get aggregated case statistics."""
    ensure_dirs()
    all_cases = list_cases()

    stats = CaseStats()
    by_severity: dict = {}
    by_scanner: dict = {}

    for case in all_cases:
        stats.total_cases += 1

        if case.status == CaseStatus.OPEN:
            stats.open_cases += 1
        else:
            stats.closed_cases += 1
            if case.bounty_amount:
                stats.total_bounty += case.bounty_amount

        # Severity breakdown
        sev = case.severity
        by_severity[sev] = by_severity.get(sev, 0) + 1

        # Scanner breakdown
        for s in case.scanners:
            by_scanner[s.name] = by_scanner.get(s.name, 0) + 1

        # Confidence accumulation for avg
        stats.avg_confidence += case.confidence

    if stats.total_cases > 0:
        stats.avg_confidence = round(stats.avg_confidence / stats.total_cases, 2)

    stats.by_severity = by_severity
    stats.by_scanner = by_scanner

    # Label distribution
    label_dist: dict[str, int] = {}
    for case in all_cases:
        lbl = case.confidence_label or "Medium"
        label_dist[lbl] = label_dist.get(lbl, 0) + 1
    stats.label_distribution = label_dist

    # Recent 5 open cases
    open_cases = [c for c in all_cases if c.status == CaseStatus.OPEN]
    open_cases.sort(key=lambda c: c.created_at, reverse=True)
    stats.recent_cases = open_cases[:5]

    return stats


def get_report_md(case_id: str) -> str | None:
    """Get the Markdown report content for a case."""
    path = _report_md_path(case_id)
    if not path.exists():
        case = get_case(case_id)
        if case is None:
            return None
        _generate_report_md(case)
    return path.read_text(encoding="utf-8")


def get_report_pdf(case_id: str) -> bytes | None:
    """Get the PDF report for a case. Generates if not exists."""
    path = _report_pdf_path(case_id)
    if not path.exists():
        case = get_case(case_id)
        if case is None:
            return None
        _generate_report_pdf(case)
    if path.exists():
        return path.read_bytes()
    return None


# ── Internal Helpers ────────────────────────────────────────────

def _write_yaml(case: Case) -> None:
    """Write a case to its meta.yaml file."""
    path = _meta_path(case.case_id)
    data = case.model_dump(mode="json")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _read_yaml(case_id: str) -> Case | None:
    """Read a case from its meta.yaml file by case_id."""
    path = _meta_path(case_id)
    return _read_yaml_from_path(case_id, path)


def _read_yaml_from_path(case_id: str, path: Path) -> Case | None:
    """Read a case from a given meta.yaml path."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return None
        # Convert scanner dicts back to ScannerFinding objects
        if "scanners" in data and data["scanners"]:
            data["scanners"] = [ScannerFinding(**s) for s in data["scanners"]]
        return Case(**data)
    except Exception as e:
        logger.error("Failed to read case YAML", case_id=case_id, path=str(path), error=str(e))
        return None


def _generate_report_md(case: Case) -> None:
    """Generate a Markdown report from a case."""
    scanners_str = "\n".join(
        f"  - **{s.name}** — `{s.detector}` (confidence: {s.confidence:.0%})"
        for s in case.scanners
    )

    status_emoji = "🟢 OPEN" if case.status == CaseStatus.OPEN else "🔴 CLOSED"
    severity_badge = {
        "Critical": "🔴 CRITICAL",
        "High": "🟠 HIGH",
        "Medium": "🟡 MEDIUM",
        "Low": "🟢 LOW",
        "Info": "🔵 INFO",
    }.get(case.severity, case.severity)

    closed_info = ""
    if case.closed_at:
        bounty_str = f"${case.bounty_amount:,.2f}" if case.bounty_amount else "$0"
        closed_info = f"""
## Closure

- **Closed at**: {case.closed_at}
- **Reason**: {case.closed_reason or "N/A"}
- **Bounty**: {bounty_str}
"""

    poc_info = ""
    if case.proof_of_concept:
        poc_info = f"""
## Proof of Concept

```solidity
{case.proof_of_concept}
```
"""

    report = f"""# Vulnerability Report: {case.title}

**Case ID**: {case.case_id} · **Status**: {status_emoji} · **Severity**: {severity_badge}

---

## Summary

| Field | Value |
|-------|-------|
| **Project** | {case.project} |
| **Contract** | `{case.contract}` |
| **Function** | `{case.function}` |
| **Line** | {case.line} |
| **Platform** | {case.platform or "N/A"} |
| **Confidence** | {case.confidence:.0%} |
| **Scanner Count** | {case.scanner_count} |
| **Created** | {case.created_at} |

## Description

{case.description}

## Scanners Involved

{scanners_str}

## Recommendation

{case.recommendation}
{poc_info}
{closed_info}
---

*Generated by Vyper — Smart Contract Bug Hunter*
"""
    path = _report_md_path(case.case_id)
    path.write_text(report, encoding="utf-8")
    logger.debug("Report MD generated", case_id=case.case_id)


def _generate_report_pdf(case: Case) -> None:
    """Generate a PDF report from the Markdown report.

    Uses weasyprint if available, falls back to a placeholder.
    """
    md_content = get_report_md(case.case_id)
    if md_content is None:
        return

    html_content = _md_to_html(md_content, case)

    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        path = _report_pdf_path(case.case_id)
        path.write_bytes(pdf_bytes)
        logger.info("PDF report generated", case_id=case.case_id)
    except ImportError:
        # Fallback: write a simple HTML file as placeholder
        html_path = _case_dir(case.case_id) / "report.html"
        html_path.write_text(html_content, encoding="utf-8")
        logger.warning("weasyprint not installed. HTML report generated instead.", case_id=case.case_id)
    except Exception as e:
        logger.error("PDF generation failed", case_id=case.case_id, error=str(e))


def _md_to_html(md_content: str, case: Case) -> str:
    """Convert Markdown report to minimal HTML for PDF generation."""
    import html as html_mod

    lines = md_content.split("\n")
    body_lines = []
    in_code = False
    in_table = False

    for line in lines:
        if line.startswith("```"):
            if in_code:
                body_lines.append("</code></pre>")
                in_code = False
            else:
                body_lines.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            body_lines.append(html_mod.escape(line))
            continue
        if line.startswith("# "):
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("| "):
            # Simple table handling with proper <table> wrapper
            if "---|---" in line:
                continue  # Skip separator row
            if not in_table:
                body_lines.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.split("|")[1:-1]]
            body_lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        elif line.startswith("- "):
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append("<br/>")
        else:
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append(f"<p>{line}</p>")

    if in_table:
        body_lines.append("</table>")

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: 'Helvetica', 'Arial', sans-serif; margin: 40px; color: #333; }}
  h1 {{ color: #6c5ce7; border-bottom: 2px solid #6c5ce7; padding-bottom: 8px; }}
  h2 {{ color: #4834d4; margin-top: 24px; }}
  h3 {{ color: #6c5ce7; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  td {{ border: 1px solid #ddd; padding: 8px; }}
  pre {{ background: #f4f4f8; padding: 12px; border-radius: 6px; overflow-x: auto; }}
  code {{ font-family: 'Courier New', monospace; font-size: 12px; }}
  li {{ margin: 4px 0; }}
  p {{ line-height: 1.6; }}
</style>
</head>
<body>
{''.join(body_lines)}
</body>
</html>"""
    return html


def _archive_to_learning(case: Case) -> None:
    """Archive closed case data to the learning directory for pattern recognition."""
    try:
        patterns_file = LEARNING_DIR / "patterns.yaml"
        patterns: list = []

        if patterns_file.exists():
            with open(patterns_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, list):
                    patterns = data

        patterns.append({
            "case_id": case.case_id,
            "severity": case.severity,
            "contract": case.contract,
            "function": case.function,
            "vulnerability_class": case.scanners[0].detector if case.scanners else "unknown",
            "scanners": [s.name for s in case.scanners],
            "confidence": case.confidence,
            "bounty": case.bounty_amount,
            "closed_reason": case.closed_reason,
            "closed_at": case.closed_at,
        })

        with open(patterns_file, "w", encoding="utf-8") as f:
            yaml.dump(patterns, f, default_flow_style=False, sort_keys=False)

        logger.debug("Case archived to learning", case_id=case.case_id)
    except Exception as e:
        logger.error("Failed to archive case to learning", case_id=case.case_id, error=str(e))
