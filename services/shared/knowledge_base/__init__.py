"""Knowledge Base — shared learning data between Classifier and Exploit.

This module provides a unified persistence layer for cross-service learning.
Both Classifier and Exploit read/write to the same ``/data/knowledge/``
volume, enabling:

- **Cross-pollination**: Exploit results improve Classifier accuracy
- **Feedback loop**: Human feedback improves Exploit hypothesis selection
- **Pattern matching**: Confirmed TPs are reusable across audits
"""

from __future__ import annotations

from .models import ConfirmedFinding, KnowledgeRecord, KnowledgeStats
from .repository import KnowledgeRepository

__all__ = [
    "ConfirmedFinding",
    "KnowledgeRecord",
    "KnowledgeStats",
    "KnowledgeRepository",
]
