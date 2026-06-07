from __future__ import annotations

import httpx
import structlog

from src.models import BugCategory, IntentClassification

log = structlog.get_logger()

INTENT_PATTERNS: dict[str, list[str]] = {
    "request_evidence": [
        "evidence", "calldata", "transaction", "tx hash", "show me",
        "demonstrate", "prove", "trace", "steps", "reproduce",
    ],
    "severity_dispute": [
        "severity", "classification", "medium", "critical", "high",
        "reclassify", "low priority", "not critical", "overstated",
    ],
    "duplicate_claim": [
        "duplicate", "already reported", "known issue", "reported by",
        "already known", "previously reported", "already submitted",
    ],
    "out_of_scope": [
        "out of scope", "not covered", "not part of", "not eligible",
        "not in scope", "outside scope", "excluded",
    ],
    "fix_question": [
        "fix", "solution", "mitigation", "proposed fix", "will this fix",
        "does this fix", "patch", "resolution",
    ],
    "general_question": [
        "how did you find", "can you explain", "methodology",
        "question", "how does", "why is", "clarify",
    ],
    "accepted": [
        "accept", "accepted", "approved", "valid finding",
        "we accept", "confirmed", "acknowledge",
    ],
    "rejected": [
        "reject", "rejected", "invalid", "not valid",
        "decline", "not reproducible", "cannot reproduce",
    ],
}

CATEGORY_KEYWORDS: dict[BugCategory, list[str]] = {
    BugCategory.reentrancy: [
        "reentrancy", "callback", "recursive call", "cross-function",
        "read-only reentrancy", "reentrant",
    ],
    BugCategory.oracle_manipulation: [
        "oracle", "price feed", "twap", "manipulation", "price impact",
        "amm", "liquidity pool",
    ],
    BugCategory.flash_loan: [
        "flash loan", "flashloan", "flash_loan", "repay", "borrow",
    ],
    BugCategory.mev: [
        "mev", "sandwich", "frontrun", "front-run", "priority gas",
        "slippage",
    ],
    BugCategory.access_control: [
        "access control", "privilege", "authorization", "role",
        "permission", "admin",
    ],
    BugCategory.overflow: [
        "overflow", "underflow", "integer overflow", "wraparound",
        "uint", "int",
    ],
    BugCategory.precision_loss: [
        "precision", "rounding", "division", "truncation", "loss",
    ],
    BugCategory.bridge: [
        "bridge", "cross-chain", "message passing", "relay", "validator",
    ],
    BugCategory.zero_day: [
        "zero-day", "novel", "new attack", "unknown", "original finding",
    ],
    BugCategory.governance: [
        "governance", "proposal", "vote", "timelock", "dao",
    ],
    BugCategory.signature_replay: [
        "signature", "replay", "nonce", "ecdsa", "cross-chain signature",
    ],
    BugCategory.storage_collision: [
        "storage", "collision", "slot", "struct packing", "overwrite",
    ],
    BugCategory.donation: [
        "donation", "inflation", "share", "liquidity", "exchange rate",
    ],
}


def _rule_based_intent(text: str) -> tuple[str, float, list[str]]:
    """Classify intent using keyword matching.

    Returns (intent, confidence, matched_keywords).
    """
    text_lower = text.lower()
    best_intent = "general_question"
    best_score = 0.0
    best_matches: list[str] = []

    for intent, keywords in INTENT_PATTERNS.items():
        matches = [kw for kw in keywords if kw.lower() in text_lower]
        if matches:
            score = len(matches) / max(len(keywords), 1)
            if intent == "accepted":
                score *= 1.2
            if score > best_score:
                best_score = min(score, 1.0)
                best_intent = intent
                best_matches = matches

    return best_intent, best_score, best_matches


def _rule_based_category(text: str) -> BugCategory | None:
    """Detect bug category from message text."""
    text_lower = text.lower()
    best_category: BugCategory | None = None
    best_score = 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw.lower() in text_lower)
        if matches > best_score:
            best_score = matches
            best_category = category

    return best_category if best_score > 0 else None


async def _ai_classify(text: str, ai_url: str, bug_category: BugCategory | None = None) -> IntentClassification | None:
    """Fallback: classify intent via AI service."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{ai_url}/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an Intent Classifier for Immunefi bug bounty messages. "
                                "Classify the intent of this message into one of: "
                                "request_evidence, severity_dispute, duplicate_claim, "
                                "out_of_scope, fix_question, general_question, accepted, rejected. "
                                "Return JSON: {\"intent\": \"...\", \"confidence\": 0.0-1.0, "
                                "\"bug_category\": \"...|null\", \"suggested_evidence\": [...]}"
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Bug category context: {bug_category.value if bug_category else 'unknown'}\n\n"
                                f"Message: {text}"
                            ),
                        },
                    ],
                    "temperature": 0.1,
                    "max_tokens": 300,
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                import json as json_mod
                try:
                    result = json_mod.loads(content)
                    cat = result.get("bug_category")
                    return IntentClassification(
                        intent=result.get("intent", "general_question"),
                        confidence=result.get("confidence", 0.5),
                        bug_category=BugCategory(cat) if cat and cat != "null" else bug_category,
                        suggested_evidence=result.get("suggested_evidence", []),
                    )
                except (json_mod.JSONDecodeError, Exception):
                    pass
    except httpx.RequestError as e:
        log.warning("intent_classifier.ai_unreachable", error=str(e))
    return None


async def classify_intent(
    message_text: str,
    ai_url: str = "http://06-ai:8000",
    bug_category: BugCategory | None = None,
) -> IntentClassification:
    """Two-layer intent classification: rule-based → AI fallback."""
    intent, confidence, matches = _rule_based_intent(message_text)

    detected_category = bug_category or _rule_based_category(message_text)

    evidence_map: dict[str, list[str]] = {
        "request_evidence": ["tx_hash", "calldata", "anvil_logs", "state_diff"],
        "severity_dispute": ["math_impact_analysis", "comparable_bugs", "market_impact"],
        "duplicate_claim": ["diff_analysis", "unique_attack_vector", "original_contribution"],
        "out_of_scope": ["program_scope", "contract_address", "accepted_precedents"],
        "fix_question": ["fixed_test_result", "gas_diff", "regression_test"],
        "general_question": ["finding_summary", "attack_timeline", "methodology"],
        "accepted": [],
        "rejected": ["rejection_reason", "improvement_suggestions"],
    }

    if confidence < 0.6:
        ai_result = await _ai_classify(message_text, ai_url, detected_category)
        if ai_result and ai_result.confidence > confidence:
            return ai_result

    return IntentClassification(
        intent=intent,
        confidence=round(confidence, 2),
        bug_category=detected_category,
        suggested_evidence=evidence_map.get(intent, ["general_evidence"]),
        required_evidence=evidence_map.get(intent, ["general_evidence"]),
        suggested_action=_get_suggested_action(intent),
    )


def _get_suggested_action(intent: str) -> str:
    actions = {
        "request_evidence": "Collect additional evidence from pipeline services",
        "severity_dispute": "Recalculate impact with MathEngine",
        "duplicate_claim": "Analyze differences with claimed duplicate",
        "out_of_scope": "Check program scope and build relevance argument",
        "fix_question": "Test proposed fix in Anvil fork",
        "general_question": "Generate technical explanation from pipeline data",
        "accepted": "Track payout and archive as reference",
        "rejected": "Analyze rejection reason and suggest improvements",
    }
    return actions.get(intent, "Review and respond")
