"""Cross-Service Intelligence Correlation — menghubungkan findings dari semua scanner.

Modul ini menganalisis findings dari 5 scanner (Slither, Echidna, Forge,
Mythril, Halmos) dan mengidentifikasi pattern yang mengindikasikan
11 bug severity tinggi/ekstrim.

Logic:
  1. Mapping findings → 11 bug categories
  2. Cross-service correlation (contoh: Slither reentrancy + Mythril SWC-107)
  3. Multi-vector chain detection
  4. Confidence scoring per bug
  5. Coverage gap analysis
"""

from __future__ import annotations

from typing import Any

# ── 11 Bug Definitions ──────────────────────────────────────

BUG_DATABASE: list[dict[str, Any]] = [
    {
        "id": "B01",
        "name": "Access Control Bypass",
        "severity": "critical",
        "swc_ids": ["SWC-105", "SWC-106", "SWC-108", "SWC-115", "SWC-121", "SWC-122"],
        "slither_detectors": ["access-control", "visibility", "unprotected-function"],
        "echidna_categories": ["access_control"],
        "halmos_categories": ["access_control"],
        "keywords": ["owner", "admin", "onlyOwner", "access", "permission", "role", "auth"],
        "description": "Attacker dapat mengakses fungsi yang seharusnya terproteksi.",
    },
    {
        "id": "B02",
        "name": "Reentrancy",
        "severity": "critical",
        "swc_ids": ["SWC-107"],
        "slither_detectors": ["reentrancy-eth", "reentrancy-no-eth"],
        "echidna_categories": ["reentrancy"],
        "halmos_categories": ["reentrancy"],
        "keywords": ["call", "send", "transfer", "reentrancy", "callback", "fallback"],
        "description": "External call sebelum state update memungkinkan recursive call.",
    },
    {
        "id": "B03",
        "name": "Flash Loan + Oracle Manipulation",
        "severity": "critical",
        "swc_ids": ["SWC-116", "SWC-119"],
        "slither_detectors": ["oracle", "timestamp"],
        "echidna_categories": ["oracle", "flash_loan"],
        "halmos_categories": ["oracle", "flash_loan"],
        "keywords": ["price", "oracle", "flash", "swap", "twap", "spot", "reserve"],
        "description": "Flash loan digunakan untuk manipulasi harga oracle.",
    },
    {
        "id": "B04",
        "name": "Logic Error Bridge / Cross-chain",
        "severity": "critical",
        "swc_ids": [],
        "slither_detectors": [],
        "echidna_categories": ["invariant_break"],
        "halmos_categories": ["assertion_violation"],
        "keywords": ["bridge", "cross", "chain", "mint", "burn", "wrapped", "lock", "unlock"],
        "description": "Logic error di bridge contract menyebabkan mint/burn tidak seimbang.",
    },
    {
        "id": "B05",
        "name": "Uninitialized Proxy",
        "severity": "critical",
        "swc_ids": ["SWC-109", "SWC-110"],
        "slither_detectors": ["uninitialized-state", "uninitialized-storage"],
        "echidna_categories": [],
        "halmos_categories": [],
        "keywords": ["initialize", "init", "proxy", "implementation", "upgrade", "UUPS"],
        "description": "Proxy contract bisa di-initialize ulang oleh attacker.",
    },
    {
        "id": "B06",
        "name": "Unchecked External Call",
        "severity": "high",
        "swc_ids": ["SWC-104"],
        "slither_detectors": ["unchecked-lowcall"],
        "echidna_categories": [],
        "halmos_categories": [],
        "keywords": ["call{value", "call(", "delegatecall", "send(", "transfer("],
        "description": "Low-level call tanpa pengecekan return value.",
    },
    {
        "id": "B07",
        "name": "Integer Overflow / Underflow",
        "severity": "high",
        "swc_ids": ["SWC-101", "SWC-102"],
        "slither_detectors": ["overflow"],
        "echidna_categories": ["arithmetic"],
        "halmos_categories": ["arithmetic"],
        "keywords": ["uint", "int", "safeMath", "overflow", "underflow", "max"],
        "description": "Operasi aritmatika yang bisa wrap-around.",
    },
    {
        "id": "B08",
        "name": "Unsafe Delegatecall",
        "severity": "high",
        "swc_ids": ["SWC-111", "SWC-112"],
        "slither_detectors": ["delegatecall", "low-level-calls"],
        "echidna_categories": [],
        "halmos_categories": [],
        "keywords": ["delegatecall", "delegate", "proxy", "implementation"],
        "description": "Delegatecall ke address yang bisa dikontrol attacker.",
    },
    {
        "id": "B09",
        "name": "Signature Replay",
        "severity": "high",
        "swc_ids": ["SWC-121"],
        "slither_detectors": [],
        "echidna_categories": [],
        "halmos_categories": [],
        "keywords": ["signature", "ecrecover", "sign", "permit", "EIP-712", "nonce"],
        "description": "Signature bisa di-replay di chain lain atau setelah digunakan.",
    },
    {
        "id": "B10",
        "name": "Front-running / Transaction Ordering",
        "severity": "high",
        "swc_ids": ["SWC-114"],
        "slither_detectors": [],
        "echidna_categories": ["dos"],
        "halmos_categories": [],
        "keywords": ["frontrun", "sandwich", "order", "race", "commit", "reveal"],
        "description": "Urutan transaksi bisa dimanipulasi oleh miner/validator.",
    },
    {
        "id": "B11",
        "name": "Arithmetic Precision Loss",
        "severity": "high",
        "swc_ids": [],
        "slither_detectors": ["divide-before-multiply"],
        "echidna_categories": ["arithmetic"],
        "halmos_categories": ["arithmetic"],
        "keywords": ["divide", "mul", "precision", "round", "scaling", "decimal"],
        "description": "Division sebelum multiplication menyebabkan rounding error.",
    },
]

# ── 11-Bug Exploit Chains ───────────────────────────────────

BUG_CHAINS: list[dict[str, Any]] = [
    {
        "name": "contract_takeover_full",
        "required_bugs": ["B08", "B05"],  # Delegatecall + Uninitialized Proxy
        "boosters": ["B01", "B06"],
        "severity": "critical",
        "confidence": 0.95,
        "narrative": [
            "Uninitialized proxy memungkinkan attacker set implementation",
            "Delegatecall mengeksekusi kode attacker di konteks proxy",
            "Storage dimodifikasi (owner, balances)",
            "Access control bypassed setelah storage takeover",
        ],
        "impact": "Complete contract takeover — all funds lost, contract controlled by attacker",
    },
    {
        "name": "reentrancy_fund_drain",
        "required_bugs": ["B02", "B01"],  # Reentrancy + Access Control
        "boosters": ["B06", "B07"],
        "severity": "critical",
        "confidence": 0.90,
        "narrative": [
            "Access control lemah atau tidak ada pada fungsi withdraw",
            "Reentrancy memungkinkan recursive withdraw sebelum balance update",
            "Unchecked call memperparah (tidak ada revert jika gagal)",
            "Dana terkuras dalam satu transaksi",
        ],
        "impact": "Complete fund drain via reentrancy + weak access control",
    },
    {
        "name": "flash_loan_price_attack",
        "required_bugs": ["B03", "B07"],  # Oracle Manupulation + Arithmetic
        "boosters": ["B11"],
        "severity": "critical",
        "confidence": 0.85,
        "narrative": [
            "Flash loan menyediakan modal besar tanpa biaya",
            "Spot price oracle dimanipulasi via swap besar",
            "Arithmetic precision loss memperparah kalkulasi harga",
            "Profit diambil sebelum flash loan dibayar kembali",
        ],
        "impact": "Financial loss via price manipulation amplified by flash loan + precision error",
    },
    {
        "name": "bridge_insolvency",
        "required_bugs": ["B04", "B09"],  # Bridge Logic + Signature Replay
        "boosters": ["B07"],
        "severity": "critical",
        "confidence": 0.80,
        "narrative": [
            "Signature replay memungkinkan mint token di chain tujuan tanpa lock di chain asal",
            "Bridge logic tidak memvalidasi uniqueness signature per chain",
            "Supply token di chain tujuan melebihi total supply sebenarnya",
            "Bridge menjadi insolven — tidak bisa redeem",
        ],
        "impact": "Bridge insolvency — tokens minted without backing, complete loss of peg",
    },
    {
        "name": "mev_sandwich_attack",
        "required_bugs": ["B10"],  # Front-running
        "boosters": ["B11"],
        "severity": "high",
        "confidence": 0.75,
        "narrative": [
            "Attacker melihat transaksi pending di mempool",
            "Buy order ditempatkan sebelum target (front-run)",
            "Harga naik karena buy order pertama",
            "Target mengeksekusi di harga lebih tinggi",
            "Sell order ditempatkan setelah target (back-run) untuk profit",
        ],
        "impact": "User loss via MEV sandwich attack — user gets worse execution price",
    },
]


def correlate_findings(
    all_findings: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Correlate findings from all scanners against 11-bug database.

    Args:
        all_findings: List of all findings from all scanners.
        tool_results: List of tool result objects.

    Returns:
        Dict with:
          - bug_coverage: per-bug detection status
          - detected_chains: exploit chains detected
          - coverage_gaps: bugs that no scanner detected
          - composite_severity: overall severity
    """
    # Extract SWC IDs and categories
    swc_found: set[str] = set()
    categories_found: dict[str, set[str]] = {
        "slither": set(), "echidna": set(), "halmos": set(),
    }
    title_text = ""

    for f in all_findings:
        swc = f.get("swc_id", "")
        if swc and swc.startswith("SWC-"):
            swc_found.add(swc.upper().strip())
        title_text += f" {f.get('title', '')} {f.get('description', '')}"

    for t in tool_results:
        tool = (t.get("tool") or "").lower()
        if tool == "slither":
            categories_found["slither"].update(t.get("categories", []))
        elif tool == "echidna":
            for f in t.get("findings", []):
                cat = f.get("failure_category", f.get("category", ""))
                if cat:
                    categories_found["echidna"].add(cat)
        elif tool == "halmos":
            for f in t.get("findings", []):
                cat = f.get("category", "")
                if cat:
                    categories_found["halmos"].add(cat)

    # Detect each bug
    bug_results: list[dict[str, Any]] = []
    for bug in BUG_DATABASE:
        evidence: list[dict[str, Any]] = []
        confidence = 0.0

        # Check 1: SWC match (Mythril)
        for swc in bug["swc_ids"]:
            if swc in swc_found:
                evidence.append({"source": "mythril_swc", "swc_id": swc, "weight": 0.9})
                confidence = max(confidence, 0.9)

        # Check 2: Category match (Echidna)
        for cat in bug["echidna_categories"]:
            if cat in categories_found["echidna"]:
                evidence.append({"source": "echidna_category", "category": cat, "weight": 0.7})
                confidence = max(confidence, 0.7)

        # Check 3: Category match (Halmos)
        for cat in bug["halmos_categories"]:
            if cat in categories_found["halmos"]:
                evidence.append({"source": "halmos_category", "category": cat, "weight": 0.75})
                confidence = max(confidence, 0.75)

        # Check 4: Keyword match (any finding title/desc)
        title_lower = title_text.lower()
        for kw in bug["keywords"]:
            if kw.lower() in title_lower:
                evidence.append({"source": "keyword_match", "keyword": kw, "weight": 0.4})
                confidence = max(confidence, 0.4)
                break  # one keyword is enough for partial match

        # Check 5: Multiple sources = higher confidence
        unique_sources = len({e["source"] for e in evidence})
        if unique_sources >= 2:
            confidence = min(confidence + 0.15, 1.0)
        if unique_sources >= 3:
            confidence = min(confidence + 0.1, 1.0)

        detected = len(evidence) > 0
        bug_results.append({
            "bug_id": bug["id"],
            "bug_name": bug["name"],
            "severity": bug["severity"],
            "detected": detected,
            "confidence": round(confidence, 3),
            "evidence": evidence,
            "evidence_count": len(evidence),
            "source_count": unique_sources,
        })

    # Detect exploit chains
    detected_bugs = {b["bug_id"] for b in bug_results if b["detected"]}
    detected_chains = _detect_chains(detected_bugs)

    # Coverage gaps
    coverage_gaps = [
        {"bug_id": b["bug_id"], "bug_name": b["bug_name"], "severity": b["severity"]}
        for b in bug_results if not b["detected"]
    ]

    # Composite severity
    critical_detected = any(
        b["detected"] for b in bug_results if b["severity"] == "critical"
    )
    high_detected = any(
        b["detected"] for b in bug_results if b["severity"] == "high"
    )

    if critical_detected:
        composite = "critical"
    elif high_detected:
        composite = "high"
    else:
        composite = "info"

    return {
        "bug_coverage": bug_results,
        "total_bugs_detected": sum(1 for b in bug_results if b["detected"]),
        "total_bugs": len(BUG_DATABASE),
        "detected_chains": detected_chains,
        "coverage_gaps": coverage_gaps,
        "composite_severity": composite,
        "summary": _generate_summary(bug_results, detected_chains),
    }


def _detect_chains(detected_bugs: set[str]) -> list[dict[str, Any]]:
    """Detect which exploit chains are possible given detected bugs."""
    results: list[dict[str, Any]] = []
    for chain in BUG_CHAINS:
        required = set(chain["required_bugs"])
        if not required.issubset(detected_bugs):
            continue

        boosters_present = set(chain["boosters"]).intersection(detected_bugs)
        booster_ratio = len(boosters_present) / max(len(chain["boosters"]), 1)
        confidence = chain["confidence"] * (0.8 + 0.2 * booster_ratio)
        confidence = min(1.0, max(0.1, confidence))

        results.append({
            "name": chain["name"],
            "severity": chain["severity"],
            "confidence": round(confidence, 3),
            "narrative": chain["narrative"],
            "impact": chain["impact"],
            "triggered_by": list(required),
            "boosters_present": list(boosters_present),
        })

    results.sort(key=lambda c: c["confidence"], reverse=True)
    return results


def _generate_summary(bug_results: list[dict[str, Any]], chains: list[dict[str, Any]]) -> str:
    detected = [b for b in bug_results if b["detected"]]
    critical = [b for b in detected if b["severity"] == "critical"]
    high = [b for b in detected if b["severity"] == "high"]

    parts = []
    if critical:
        parts.append(f"🔴 {len(critical)} critical bug(s) detected: {', '.join(b['bug_name'] for b in critical)}")
    if high:
        parts.append(f"🟠 {len(high)} high bug(s) detected: {', '.join(b['bug_name'] for b in high)}")
    if chains:
        parts.append(f"⛓️ {len(chains)} exploit chain(s) possible")
    if not detected:
        parts.append("✅ No high/critical bugs detected from 11-bug database")

    return " | ".join(parts)
