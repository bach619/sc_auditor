"""Cairo detector registry — maps detector names to detector classes."""

from __future__ import annotations

from typing import Any, Dict, List

from src.detectors.access_control import AccessControlDetector
from src.detectors.arithmetic_overflow import ArithmeticOverflowDetector
from src.detectors.base import BaseCairoDetector
from src.detectors.event_emission import EventEmissionDetector
from src.detectors.oracle_manipulation import OracleManipulationDetector
from src.detectors.reentrancy import ReentrancyDetector
from src.detectors.storage_collision import StorageCollisionDetector
from src.detectors.unchecked_return import UncheckedReturnDetector
from src.detectors.upgrade_safety import UpgradeSafetyDetector

DETECTOR_REGISTRY: dict[str, BaseCairoDetector] = {
    "access_control": AccessControlDetector(),
    "storage_collision": StorageCollisionDetector(),
    "arithmetic_overflow": ArithmeticOverflowDetector(),
    "reentrancy": ReentrancyDetector(),
    "unchecked_return": UncheckedReturnDetector(),
    "oracle_manipulation": OracleManipulationDetector(),
    "event_emission": EventEmissionDetector(),
    "upgrade_safety": UpgradeSafetyDetector(),
}


def run_detector(name: str, ir_contract: dict[str, Any]) -> list[dict[str, Any]]:
    detector = DETECTOR_REGISTRY.get(name)
    if not detector:
        return []
    return detector.analyze(ir_contract)
