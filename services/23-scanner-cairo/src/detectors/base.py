"""Base Cairo detector abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseCairoDetector(ABC):
    name: str
    description: str
    severity_focus: str = "medium"
    category: str = "general"

    @abstractmethod
    def analyze(self, ir_contract: dict[str, Any]) -> list[dict[str, Any]]:
        ...
