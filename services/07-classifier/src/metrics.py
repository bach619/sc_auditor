"""Metrics tracking for the Vyper Classifier Service.

Tracks TP/FP/TN/FN counts, computes standard ML classification metrics
(precision, recall, F1), provides per-tool breakdowns, and maintains
time-series data for trend analysis.

Metrics are stored as JSON at ``/data/classifier/metrics.json`` and follow
the data model defined in the architecture specification §7.3.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from src.models import Classification

log = structlog.get_logger()

# ── Constants ────────────────────────────────────────────────────────────

METRICS_FILE = Path("/data/classifier/metrics.json")

# Weights for the overall score computation
OVERALL_PRECISION_WEIGHT: float = 0.35
OVERALL_RECALL_WEIGHT: float = 0.35
OVERALL_COVERAGE_WEIGHT: float = 0.30


# ── Helpers ──────────────────────────────────────────────────────────────


def _today_str() -> str:
    """Return today's UTC date as ``YYYY-MM-DD``."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _load_metrics() -> dict[str, Any]:
    """Load metrics from disk. Returns default structure if missing."""
    if METRICS_FILE.exists():
        try:
            with open(METRICS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("metrics_load_error", error=str(exc))
    return {
        "totals": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
        "by_tool": {},
        "daily": {},
    }


def _save_metrics(metrics: dict[str, Any]) -> bool:
    """Persist metrics atomically to disk."""
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = METRICS_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        tmp.replace(METRICS_FILE)
        return True
    except OSError as exc:
        log.error("metrics_save_error", error=str(exc))
        if tmp.exists():
            tmp.unlink()
        return False


def _compute_precision(tp: int, fp: int) -> float:
    """Precision = TP / (TP + FP). Returns 0 if denominator is 0."""
    denominator = tp + fp
    return tp / denominator if denominator > 0 else 0.0


def _compute_recall(tp: int, fn: int) -> float:
    """Recall = TP / (TP + FN). Returns 0 if denominator is 0."""
    denominator = tp + fn
    return tp / denominator if denominator > 0 else 0.0


def _compute_f1(precision: float, recall: float) -> float:
    """F1 = 2 * (P * R) / (P + R). Returns 0 if denominator is 0."""
    denominator = precision + recall
    return 2 * precision * recall / denominator if denominator > 0 else 0.0


def _compute_accuracy(tp: int, tn: int, fp: int, fn: int) -> float:
    """Accuracy = (TP + TN) / (TP + TN + FP + FN). Returns 0 if total is 0."""
    total = tp + tn + fp + fn
    return (tp + tn) / total if total > 0 else 0.0


def _compute_overall(precision: float, recall: float, accuracy: float) -> float:
    """Weighted composite score combining precision, recall, and accuracy."""
    return (
        OVERALL_PRECISION_WEIGHT * precision
        + OVERALL_RECALL_WEIGHT * recall
        + OVERALL_COVERAGE_WEIGHT * accuracy
    )


# ── MetricsTracker ───────────────────────────────────────────────────────


class MetricsTracker:
    """Tracks and computes classification accuracy metrics.

    Records every classification decision, maintains running totals,
    and computes standard ML performance metrics. Supports per-tool
    breakdowns and time-series trend data.
    """

    def __init__(self) -> None:
        self._metrics: dict[str, Any] = _load_metrics()
        log.info(
            "metrics_tracker_initialized",
            totals=self._metrics["totals"],
        )

    # ── Recording ────────────────────────────────────────────────────────

    def record(
        self,
        finding_id: str,
        classification: Classification,
        is_correct: bool,
        tool_name: str | None = None,
    ) -> None:
        """Record a classification outcome and update all metrics.

        Updates:
        - Running TP/FP/TN/FN totals
        - Per-tool breakdown (if tool_name is provided)
        - Daily time-series snapshot

        Args:
            finding_id: Unique identifier of the classified finding.
            classification: The classification that was made.
            is_correct: Whether the classification was correct (ground truth).
            tool_name: Name of the tool that produced the finding (optional).
        """
        today = _today_str()
        is_positive = classification in (
            Classification.TRUE_POSITIVE,
            Classification.FALSE_POSITIVE,
        )

        # Map the combination to the appropriate metric bucket
        if is_positive and is_correct:
            bucket = "tp"
        elif is_positive and not is_correct:
            bucket = "fp"
        elif not is_positive and is_correct:
            bucket = "tn"
        elif not is_positive and not is_correct:
            bucket = "fn"
        else:
            log.warning("unexpected_classification_combo", classification=classification.value)
            return

        # Update totals
        self._metrics["totals"][bucket] += 1

        # Update per-tool breakdown
        if tool_name:
            by_tool = self._metrics["by_tool"]
            if tool_name not in by_tool:
                by_tool[tool_name] = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
            by_tool[tool_name][bucket] += 1

        # Update daily snapshot
        if today not in self._metrics["daily"]:
            self._metrics["daily"][today] = {
                "tp": 0, "fp": 0, "tn": 0, "fn": 0,
                "precision": 0.0, "recall": 0.0, "f1_score": 0.0,
                "accuracy": 0.0, "overall_score": 0.0,
            }
        self._metrics["daily"][today][bucket] += 1

        # Recompute derived metrics for today
        daily = self._metrics["daily"][today]
        tp, fp, tn, fn = daily["tp"], daily["fp"], daily["tn"], daily["fn"]
        daily["precision"] = round(_compute_precision(tp, fp), 4)
        daily["recall"] = round(_compute_recall(tp, fn), 4)
        daily["f1_score"] = round(_compute_f1(daily["precision"], daily["recall"]), 4)
        daily["accuracy"] = round(_compute_accuracy(tp, tn, fp, fn), 4)
        daily["overall_score"] = round(
            _compute_overall(daily["precision"], daily["recall"], daily["accuracy"]),
            4,
        )

        _save_metrics(self._metrics)
        log.debug(
            "metrics_recorded",
            finding_id=finding_id,
            bucket=bucket,
            tool=tool_name,
        )

    # ── Querying ─────────────────────────────────────────────────────────

    def get_metrics(self) -> dict[str, Any]:
        """Return the current aggregate metrics.

        Returns:
            Dictionary containing:
            - tp, fp, tn, fn: Total counts
            - precision, recall, f1_score, accuracy, overall_score: Computed metrics
            - total_classified: Sum of all classifications
        """
        totals = self._metrics["totals"]
        tp = totals["tp"]
        fp = totals["fp"]
        tn = totals["tn"]
        fn = totals["fn"]

        precision = _compute_precision(tp, fp)
        recall = _compute_recall(tp, fn)
        f1 = _compute_f1(precision, recall)
        accuracy = _compute_accuracy(tp, tn, fp, fn)
        overall = _compute_overall(precision, recall, accuracy)

        return {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "accuracy": round(accuracy, 4),
            "overall_score": round(overall, 4),
            "total_classified": tp + fp + tn + fn,
        }

    def get_tool_metrics(self) -> list[dict[str, Any]]:
        """Return metrics broken down by scanning tool.

        Returns:
            List of per-tool metric dictionaries with computed precision,
            recall, and F1 scores.
        """
        results: list[dict[str, Any]] = []
        by_tool = self._metrics.get("by_tool", {})

        for tool_name, counts in sorted(by_tool.items()):
            tp = counts["tp"]
            fp = counts["fp"]
            tn = counts["tn"]
            fn = counts["fn"]

            precision = _compute_precision(tp, fp)
            recall = _compute_recall(tp, fn)
            f1 = _compute_f1(precision, recall)

            results.append({
                "tool": tool_name,
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4),
                "total_findings": tp + fp + tn + fn,
            })

        # Only return tool-average fields if there's at least one tool
        if results:
            avg_precision = sum(r["precision"] for r in results) / len(results)
            avg_recall = sum(r["recall"] for r in results) / len(results)
            avg_f1 = sum(r["f1_score"] for r in results) / len(results)
        else:
            avg_precision = avg_recall = avg_f1 = 0.0

        return {
            "tools": results,
            "tool_count": len(results),
            "average_tool_precision": round(avg_precision, 4),
            "average_tool_recall": round(avg_recall, 4),
            "average_tool_f1": round(avg_f1, 4),
        }

    def get_trend(self, days: int = 30) -> list[dict[str, Any]]:
        """Return daily metrics snapshots over the last N days.

        Args:
            days: Number of days to look back from today.

        Returns:
            List of daily metric snapshots, sorted chronologically.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        daily = self._metrics.get("daily", {})

        snapshots: list[dict[str, Any]] = []
        for date_str in sorted(daily.keys()):
            if date_str >= cutoff_str:
                snapshots.append({
                    "date": date_str,
                    **daily[date_str],
                })
        return snapshots
