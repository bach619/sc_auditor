"""ComputeMetricsSkill — accuracy/precision/recall metrics."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class ComputeMetricsSkill(BaseSkill):
    """Compute accuracy, precision, recall, and F1 from classification results."""

    @property
    def name(self) -> str:
        return "compute_metrics"

    @property
    def description(self) -> str:
        return (
            "Compute classification performance metrics from labeled results. "
            "Returns accuracy, precision, recall, F1-score, and confusion matrix. "
            "Supports ground-truth comparison when available."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "classifications": {
                    "type": "array",
                    "description": "List of classification results with predicted labels",
                },
                "ground_truth": {
                    "type": "array",
                    "description": "Optional list of ground truth labels for evaluation",
                },
                "true_positive_label": {
                    "type": "string",
                    "description": "Label used for true positive (default: TP)",
                },
            },
            "required": ["classifications"],
        }

    @property
    def category(self) -> str:
        return "classification"

    async def run(
        self,
        classifications: list[dict[str, Any]],
        ground_truth: list[str] | None = None,
        true_positive_label: str = "TP",
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..metrics import MetricsTracker

        tracker = MetricsTracker()
        summary = tracker.get_summary()

        predicted = []
        for c in classifications:
            label = c.get("classification", c.get("label", "unknown"))
            predicted.append(label)

        if ground_truth and len(ground_truth) == len(predicted):
            tp = sum(1 for g, p in zip(ground_truth, predicted) if g == true_positive_label and p == true_positive_label)
            fp = sum(1 for g, p in zip(ground_truth, predicted) if g != true_positive_label and p == true_positive_label)
            tn = sum(1 for g, p in zip(ground_truth, predicted) if g != true_positive_label and p != true_positive_label)
            fn = sum(1 for g, p in zip(ground_truth, predicted) if g == true_positive_label and p != true_positive_label)

            accuracy = (tp + tn) / len(ground_truth) if ground_truth else 0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            return {
                "skill": "compute_metrics",
                "total_classifications": len(predicted),
                "accuracy": round(accuracy, 4),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4),
                "confusion_matrix": {
                    "true_positives": tp,
                    "false_positives": fp,
                    "true_negatives": tn,
                    "false_negatives": fn,
                },
                "tp_rate": round(tp / len(ground_truth), 4) if ground_truth else 0,
                "fp_rate": round(fp / len(ground_truth), 4) if ground_truth else 0,
            }

        return {
            "skill": "compute_metrics",
            "total_classifications": len(predicted),
            "class_distribution": {
                "tp_count": predicted.count(true_positive_label),
                "fp_count": predicted.count("FP"),
                "fptn_count": predicted.count("FP-TN"),
                "unknown_count": predicted.count("unknown"),
            },
            "service_metrics": summary,
            "note": "Ground truth not provided — showing distribution only. Supply ground_truth for full metrics.",
        }
