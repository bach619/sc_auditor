"""Jinja2 custom filters for report templates.

Provides severity badges, status badges, and other formatting utilities
used by both the Immunefi and full report templates.
"""

from __future__ import annotations

from typing import Any

SEVERITY_BADGES: dict[str, str] = {
    "critical": "🟣 CRITICAL",
    "high": "🔴 HIGH",
    "medium": "🟠 MEDIUM",
    "low": "🟡 LOW",
    "informational": "⚪ INFO",
    "info": "⚪ INFO",
}

STATUS_BADGES: dict[str, str] = {
    "true_positive": "🟢 True Positive",
    "true_negative": "✅ True Negative",
    "false_positive": "🔴 False Positive",
    "false_negative": "🟡 False Negative",
    "tp": "🟢 TP",
    "fp": "🔴 FP",
    "tn": "✅ TN",
    "fn": "🟡 FN",
}


def severity_badge(value: str) -> str:
    """Render a severity level as an emoji badge string.

    Args:
        value: Severity string (case-insensitive).

    Returns:
        Badge string like ``"🟣 CRITICAL"``.
    """
    return SEVERITY_BADGES.get(value.lower(), f"⚪ {value.upper()}")


def status_badge(value: str) -> str:
    """Render a classification status as an emoji badge string.

    Args:
        value: Classification status string.

    Returns:
        Badge string like ``"🟢 True Positive"``.
    """
    return STATUS_BADGES.get(value.lower(), value)


def ascii_severity_chart(severity_counts: list[tuple[str, int]]) -> str:
    """Generate an ASCII bar chart from severity counts.

    Args:
        severity_counts: List of ``(severity_label, count)`` tuples
                         ordered by severity (critical first).

    Returns:
        A multi-line ASCII bar chart string.
    """
    if not severity_counts:
        return "  (no findings)"

    max_count = max(c for _, c in severity_counts)
    if max_count == 0:
        return "  (no findings)"

    bar_width = 20
    lines: list[str] = []
    for label, count in severity_counts:
        filled = round((count / max_count) * bar_width) if max_count > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"  {label:20s} │{bar}│ {count}")

    return "\n".join(lines)


def format_number(value: Any) -> str:
    """Format a number with thousands separators.

    Args:
        value: Number to format.

    Returns:
        Formatted string like ``"1,234"``.
    """
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def register_filters(env: Any) -> None:
    """Register all custom filters on a Jinja2 environment.

    Args:
        env: A ``jinja2.Environment`` instance.
    """
    env.filters["badge"] = severity_badge
    env.filters["status_badge"] = status_badge
    env.filters["ascii_chart"] = ascii_severity_chart
    env.filters["format_number"] = format_number
