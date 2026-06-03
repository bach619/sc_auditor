"""Base Cairo detector abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseCairoDetector(ABC):
    name: str
    description: str
    severity_focus: str = "medium"
    category: str = "general"

    @abstractmethod
    def analyze(self, ir_contract: Dict[str, Any]) -> List[Dict[str, Any]]:
        ...
