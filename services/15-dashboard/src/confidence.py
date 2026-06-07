"""Confidence Scoring Engine — Agenda 06: Confidence atas Temuan.

Multi-factor confidence calculation system that converts scanner findings
into a 4-label scale (Low → Medium → High → Critical) based on:

    A. Jumlah Scanner  (1=Medium, 2=High, 3+=Critical)
    B. PoC Exploit     (+1 level jika ada)
    C. Pattern Learning (weight ≥1 → +1 level, weight=-1 → -1 level)
    D. Kategori Vuln   (Info/Gas → paksa Low)

All factors stack sequentially up to the Critical cap.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(service="confidence")

# ── Label Definition ──────────────────────────────────────────────

class ConfidenceLabel(StrEnum):
    """Empat label confidence — hanya ini, tidak ada yang lain."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

# Urutan sorting: Critical = 0 (paling atas), Low = 3 (paling bawah)
LABEL_ORDER: dict[str, int] = {
    "Critical": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
}

LABEL_COLORS: dict[str, str] = {
    "Critical": "bg-red-500/20 text-red-400",
    "High": "bg-orange-500/20 text-orange-400",
    "Medium": "bg-yellow-500/20 text-yellow-400",
    "Low": "bg-gray-500/20 text-gray-400",
}

# Kategori yang otomatis turun ke Low
LOW_OVERRIDE_CATEGORIES = {
    "informational",
    "best-practice",
    "gas-optimization",
    "gas",
    "optimization",
    "naming-convention",
    "unused-return",
    "unused-import",
    "pragma",
    "style-guide",
}


def hitung_confidence_label(
    scanner_count: int,
    has_poc: bool = False,
    pattern_weight: int = 0,
    vuln_category: str = "unknown",
) -> tuple[ConfidenceLabel, list[str]]:
    """Hitung confidence label berdasarkan 4 faktor (Agenda 06 spec).

    Parameters
    ----------
    scanner_count:
        Berapa scanner independent yang menemukan bug ini.
    has_poc:
        Apakah Proof-of-Concept exploit berhasil dieksekusi.
    pattern_weight:
        Bobot dari learning/patterns.yaml:
            >= 1   → booster +1 level (pernah confirmed)
            0      → netral (pola baru)
            < 0    → turun 1 level (pernah false positive)
    vuln_category:
        Kategori vulnerability (reentrancy, access-control, gas, dll).

    Returns
    -------
    Tuple[ConfidenceLabel, list[str]]
        Label final + daftar faktor (untuk ditampilkan di UI).
    """
    factors: list[str] = []

    # ── Faktor D (FIRST) — Kategori override ─────────────────
    cat_lower = vuln_category.lower().replace("_", "-")
    if cat_lower in LOW_OVERRIDE_CATEGORIES:
        factors.append(f"Kategori '{vuln_category}' bersifat informational/gas optimization")
        return ConfidenceLabel.LOW, factors

    # ── Faktor A: Jumlah Scanner ─────────────────────────────
    if scanner_count >= 3:
        label = ConfidenceLabel.CRITICAL
        factors.append(f"{scanner_count} scanner mendeteksi")
    elif scanner_count == 2:
        label = ConfidenceLabel.HIGH
        factors.append(f"{scanner_count} scanner mendeteksi")
    elif scanner_count == 1:
        label = ConfidenceLabel.MEDIUM
        factors.append(f"{scanner_count} scanner mendeteksi")
    else:
        label = ConfidenceLabel.LOW
        factors.append("Tidak ada scanner")

    # ── Faktor B: PoC Exploit (naik 1 level, cap Critical) ──
    if has_poc and label != ConfidenceLabel.CRITICAL:
        if label == ConfidenceLabel.MEDIUM:
            label = ConfidenceLabel.HIGH
        elif label == ConfidenceLabel.HIGH:
            label = ConfidenceLabel.CRITICAL
        factors.append("PoC exploit berhasil dibuat")

    # ── Faktor C: Pattern Learning (naik/turun 1, cap Low/Critical) ──
    if pattern_weight >= 1:
        if label == ConfidenceLabel.MEDIUM:
            label = ConfidenceLabel.HIGH
            factors.append("Pola vulnerability ini pernah confirmed sebelumnya")
        elif label == ConfidenceLabel.HIGH:
            label = ConfidenceLabel.CRITICAL
            factors.append("Pola vulnerability ini pernah confirmed sebelumnya")
        # Jika sudah Critical, booster diabaikan (cap)
    elif pattern_weight <= -1:
        if label == ConfidenceLabel.HIGH:
            label = ConfidenceLabel.MEDIUM
            factors.append("Pola vulnerability ini pernah false positive")
        elif label == ConfidenceLabel.MEDIUM:
            label = ConfidenceLabel.LOW
            factors.append("Pola vulnerability ini pernah false positive")
        # Jika sudah Low, tidak bisa turun lagi

    return label, factors


# ── Pattern Learning (patterns.yaml) ───────────────────────────────

def _pattern_id_from_case(vuln_class: str, contract: str, function: str) -> str:
    """Generate pattern ID dari case attributes."""
    return f"{vuln_class}-{contract}-{function}".lower().replace(" ", "-")[:120]


def load_patterns(patterns_path: Path) -> list[dict[str, Any]]:
    """Load patterns dari patterns.yaml. Return empty list jika tidak ada."""
    if not patterns_path.exists():
        return []
    try:
        with open(patterns_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        logger.error("Failed to load patterns", path=str(patterns_path), error=str(e))
        return []


def get_pattern_weight(
    vuln_class: str,
    contract: str,
    function: str,
    patterns: list[dict[str, Any]],
) -> int:
    """Cari bobot pattern berdasarkan vuln_class + contract + function.

    Returns
    -------
    int
        - Bobot akumulasi (>=1 = confirmed, 0 = baru, <=-1 = false positive)
        - Default 0 jika belum ada pattern match.
    """
    if not patterns:
        return 0

    pattern_id = _pattern_id_from_case(vuln_class, contract, function)

    # Exact match berdasarkan pattern_id
    for p in patterns:
        pid = p.get("pattern_id", "")
        if pid == pattern_id:
            return p.get("weight", 0)

    # Fallback: partial match berdasarkan vuln_class saja
    matching = [p for p in patterns if p.get("vulnerability", "") == vuln_class]
    if matching:
        total_weight = sum(p.get("weight", 0) for p in matching)
        return total_weight

    return 0


def update_pattern_learning(
    vuln_class: str,
    contract: str,
    function: str,
    is_confirmed: bool,
    case_id: str,
    bounty: float | None = None,
    patterns_path: Path | None = None,
) -> None:
    """Update learning patterns.yaml setelah case di-close.

    - confirmed → weight +1
    - false positive / rejected → weight -1

    Parameters
    ----------
    vuln_class:
        Detector name dari scanner (e.g. "reentrancy", "access-control").
    contract:
        Contract name (e.g. "Vault.sol").
    function:
        Function name (e.g. "withdraw").
    is_confirmed:
        True jika case diterima (bounty didapat).
    case_id:
        ID case untuk referensi.
    bounty:
        Bounty amount (optional, untuk confirmed case).
    patterns_path:
        Path ke patterns.yaml. Default ~/.sc_auditor/learning/patterns.yaml.
    """
    if patterns_path is None:
        from src.storage import LEARNING_DIR  # lazy import
        patterns_path = LEARNING_DIR / "patterns.yaml"

    try:
        patterns = load_patterns(patterns_path)
        pattern_id = _pattern_id_from_case(vuln_class, contract, function)

        # Cari pattern yang sudah ada
        existing = None
        for p in patterns:
            if p.get("pattern_id") == pattern_id:
                existing = p
                break

        if existing is not None:
            # Update existing pattern
            delta = 1 if is_confirmed else -1
            existing["weight"] = existing.get("weight", 0) + delta
            if case_id not in existing.get("cases", []):
                existing.setdefault("cases", []).append(case_id)
            if is_confirmed and bounty is not None:
                # Track highest bounty for this pattern
                existing["bounty"] = max(existing.get("bounty", 0) or 0, bounty)
            existing["status"] = "confirmed" if is_confirmed else "false_positive"
        else:
            # Create new pattern entry
            pattern = {
                "pattern_id": pattern_id,
                "vulnerability": vuln_class,
                "contract": contract,
                "function": function,
                "status": "confirmed" if is_confirmed else "false_positive",
                "weight": 1 if is_confirmed else -1,
                "bounty": bounty if is_confirmed else None,
                "cases": [case_id],
            }
            patterns.append(pattern)

        # Write back
        patterns_path.parent.mkdir(parents=True, exist_ok=True)
        with open(patterns_path, "w", encoding="utf-8") as f:
            yaml.dump(patterns, f, default_flow_style=False, sort_keys=False)

        logger.debug(
            "Pattern learning updated",
            pattern_id=pattern_id,
            weight=existing["weight"] if existing else (1 if is_confirmed else -1),
            is_confirmed=is_confirmed,
            case_id=case_id,
        )

    except Exception as e:
        logger.error(
            "Failed to update pattern learning",
            pattern_id=_pattern_id_from_case(vuln_class, contract, function),
            case_id=case_id,
            error=str(e),
        )
