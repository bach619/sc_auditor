from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from src.models import Submission

log = structlog.get_logger()

CATEGORY_ARGUMENT_TEMPLATES: dict[str, str] = {
    "reentrancy": (
        "This is a reentrancy vulnerability:\n"
        "- Attack vector: {attack_vector}\n"
        "- Call graph depth: {call_depth} levels\n"
        "- Affected functions: {affected_functions}\n"
        "- Read-only reentrancy: {is_read_only}\n"
        "- Cross-function reentrancy: {is_cross_function}\n\n"
        "The PoC demonstrates a full exploit flow: {exploit_steps}\n\n"
        "What makes this particularly dangerous is {unique_aspect}."
    ),
    "oracle_manipulation": (
        "This oracle manipulation attack exploits {oracle_type} price feeds.\n\n"
        "Key parameters:\n"
        "- Manipulation cost: ${manipulation_cost:,.0f}\n"
        "- Profit at manipulation cost: ${profit_at_cost:,.0f}\n"
        "- Break-even manipulation size: {break_even_size}\n"
        "- TWAP window exploited: {twap_window} blocks\n\n"
        "The exploit is economically viable because {economic_argument}."
    ),
    "flash_loan": (
        "This flash loan attack requires:\n"
        "- Flash loan amount: ${flash_loan_amount:,.0f}\n"
        "- Protocol TVL affected: ${affected_tvl:,.0f}\n"
        "- Net profit: ${net_profit:,.0f}\n"
        "- Steps: {exploit_steps}\n\n"
        "The attack is {is_profitable} because {profit_analysis}."
    ),
    "mev": (
        "This MEV vulnerability enables:\n"
        "- MEV score: {mev_score}/1.0\n"
        "- Sandwich profit per block: ${sandwich_profit:,.0f}\n"
        "- Affected user loss per tx: ${user_loss:,.0f}\n"
        "- Probability of exploitation: {probability}\n\n"
        "The key insight is {mev_insight}."
    ),
    "overflow": (
        "Integer overflow/underflow:\n"
        "- Variable: {variable}\n"
        "- Type: {var_type}\n"
        "- Overflow value: {overflow_value}\n"
        "- Trigger condition: {trigger_condition}\n"
        "- Max exploit value: ${max_value:,.0f}\n\n"
        "The SAT solver confirmed: {sat_result}"
    ),
    "precision_loss": (
        "Precision loss in fee calculation:\n"
        "- Function: {function}\n"
        "- Division order: {division_order}\n"
        "- Loss per transaction: {loss_per_tx}\n"
        "- Accumulated loss over {time_period}: {accumulated_loss}\n"
        "- Affected users: {affected_users}\n\n"
        "The fixed-point analyzer shows {fp_analysis}."
    ),
    "bridge": (
        "Cross-chain bridge vulnerability:\n"
        "- Source chain: {source_chain}\n"
        "- Destination chain: {dest_chain}\n"
        "- Bridge type: {bridge_type}\n"
        "- Validator set size: {validator_count}\n"
        "- Compromised validators needed: {needed_validators}\n\n"
        "The attack path: {attack_path}"
    ),
    "zero_day": (
        "NOVEL VULNERABILITY — No prior art found.\n\n"
        "This is a novel attack pattern because:\n"
        "1. {novelty_point_1}\n"
        "2. {novelty_point_2}\n"
        "3. {novelty_point_3}\n\n"
        "Search conducted across: {search_sources}\n"
        "Closest prior art: {closest_prior_art} (but differs because {difference})\n\n"
        "Full mathematical proof available: {math_proof_available}"
    ),
    "governance": (
        "Governance attack via {attack_vector}:\n"
        "- Proposal ID: {proposal_id}\n"
        "- Required votes: {required_votes}\n"
        "- Attacker-controlled votes: {attacker_votes}\n"
        "- Vote manipulation: {vote_manipulation_method}\n"
        "- Time lock bypass: {timelock_bypass}\n"
        "- Funds at risk: ${funds_at_risk:,.0f}"
    ),
    "signature_replay": (
        "Signature replay vulnerability:\n"
        "- Same signature valid on: {chain_ids}\n"
        "- Reusable value: ${reusable_value:,.0f}\n"
        "- ECDSA nonce: {nonce} (reused across chains)\n"
        "- Affected functions: {affected_functions}\n\n"
        "The modular arithmetic proof: {modular_proof}"
    ),
    "storage_collision": (
        "Storage collision via struct packing:\n"
        "- Contract: {contract}\n"
        "- Slot: {slot}: {variable_1} collides with {variable_2}\n"
        "- LLL-reduced basis: {lll_basis}\n"
        "- Exploit: write to {variable_1} corrupts {variable_2}\n"
        "- Impact: {impact}"
    ),
    "donation": (
        "Donation attack / share inflation:\n"
        "- Exchange rate manipulation: {exchange_rate_change}\n"
        "- Donation amount: ${donation_amount:,.0f}\n"
        "- Share inflation: {share_inflation}\n"
        "- Victims: {victim_count} LP holders\n"
        "- Profit: ${profit:,.0f}"
    ),
    "access_control": (
        "Access control bypass:\n"
        "- Missing check in: {function}\n"
        "- Required role: {required_role}\n"
        "- Current access: {current_access}\n"
        "- Exploitable by: {exploitable_by}\n"
        "- Funds at risk: ${funds_at_risk:,.0f}\n"
        "- Privilege escalation path: {escalation_path}"
    ),
}

TEMPLATE_FALLBACKS: dict[str, dict[str, str]] = {
    "request_evidence": {
        "default": (
            "Thank you for your review. Regarding your request for additional "
            "evidence, please find attached the following:\n\n"
            "1. Transaction hash: {tx_hash}\n"
            "2. Complete calldata\n"
            "3. Forge test output showing the exploit\n\n"
            "The exploit was tested in an isolated Anvil environment (no real "
            "funds at risk). Please let me know if you need any clarification."
        ),
        "reentrancy": (
            "Thank you for your review. Please find the reentrancy-specific evidence:\n\n"
            "1. Full call graph showing reentrancy loop ({call_depth} levels)\n"
            "2. State diff at each call frame\n"
            "3. Reentrancy guard bypass demonstration\n"
            "4. Anvil trace with exact instruction stepping\n\n"
            "The exploit was tested with both read-only and write reentrancy patterns."
        ),
        "oracle_manipulation": (
            "Thank you for your review. Attached is the oracle manipulation evidence:\n\n"
            "1. Price impact graph\n"
            "2. Manipulation cost breakdown: ${manipulation_cost:,.0f}\n"
            "3. TWAP window analysis ({twap_window} blocks)\n"
            "4. MathEngine profit calculation\n\n"
            "The economic analysis confirms the attack is profitable at {break_even_size} manipulation size."
        ),
        "zero_day": (
            "Thank you for your review. This is a NOVEL vulnerability finding.\n\n"
            "Attached evidence:\n"
            "1. Full mathematical proof of the exploit\n"
            "2. Prior art search results (no matching findings)\n"
            "3. Multiple PoC variants demonstrating different attack paths\n"
            "4. Anvil fork simulation with exact fund flows\n\n"
            "I believe this represents an original contribution to the program's security."
        ),
        "overflow": (
            "Thank you for your review. Attached are the overflow-specific details:\n\n"
            "1. SAT solver output confirming exact overflow values\n"
            "2. Boundary condition analysis\n"
            "3. Minimal PoC demonstrating the overflow\n"
            "4. Maximum extractable value calculation\n\n"
            "The overflow is triggered when {trigger_condition}."
        ),
    },
    "severity_dispute": {
        "default": (
            "I appreciate the thorough review. Regarding the severity "
            "classification:\n\n"
            "1. The maximum potential loss is ${max_loss:,.0f}\n"
            "2. This affects {affected_users} users\n"
            "3. The exploit requires no special privileges\n\n"
            "Based on Immunefi's severity guidelines, this meets the criteria "
            "for {current_severity}."
        ),
        "oracle_manipulation": (
            "I respectfully disagree with the severity classification.\n\n"
            "- Manipulation cost (${manipulation_cost:,.0f})\n"
            "- Profit potential (${profit:,.0f})\n\n"
            "This clearly meets the criteria for {current_severity} severity."
        ),
        "reentrancy": (
            "Regarding the severity classification:\n\n"
            "1. The reentrancy allows draining {max_drainable} per transaction\n"
            "2. No reentrancy guard present\n"
            "3. Can be combined with flash loan for amplified impact\n\n"
            "Per Immunefi's reentrancy severity matrix, this is {current_severity}."
        ),
        "zero_day": (
            "I understand the severity concern, but this novel vulnerability "
            "warrants {current_severity} classification:\n\n"
            "1. No existing mitigations exist for this attack pattern\n"
            "2. Maximum theoretical loss: ${max_loss:,.0f}\n"
            "3. Novel attack vector means no current monitoring covers it\n\n"
            "The novelty premium is justified by the lack of existing defenses."
        ),
    },
}


async def generate_draft(
    submission: Submission,
    immunefi_message: str,
    intent: str,
    evidence: dict[str, Any],
    ai_url: str = "http://06-ai:8000",
    tone: str = "professional",
) -> str:
    """Generate a draft response using AI (primary) or template fallback."""
    category = submission.bug_category.value if hasattr(submission.bug_category, "value") else str(submission.bug_category)
    cat_template = CATEGORY_ARGUMENT_TEMPLATES.get(category, "")
    category_data = evidence.get("category_data", {})
    try:
        category_arguments = cat_template.format(**category_data) if cat_template else ""
    except (KeyError, ValueError):
        category_arguments = cat_template

    prompt = (
        f"You are a professional smart contract security researcher "
        f"responding to Immunefi's bug bounty team.\n\n"
        f"## Finding Context\n"
        f"Title: {submission.title}\n"
        f"Bug Category: {category}\n"
        f"Severity: {submission.severity}\n"
        f"Program: {submission.program_slug}\n\n"
        f"## Category-Specific Analysis\n"
        f"{category_arguments}\n\n"
        f"## Immunefi's Message\n"
        f'"{immunefi_message}"\n\n'
        f"## Detected Intent\n"
        f"{intent}\n\n"
        f"## Available Evidence\n"
        f"{json.dumps(evidence, indent=2)}\n\n"
        f"## Instructions\n"
        f"Generate a professional response that:\n"
        f"1. Acknowledges Immunefi's message professionally\n"
        f"2. References the category-specific analysis\n"
        f"3. Uses technical language appropriate for {category} vulnerabilities\n"
        f"4. Is concise (under 300 words unless necessary)\n"
        f"5. Maintains a respectful, collaborative tone\n\n"
        f"Return ONLY the response text, no additional commentary."
    )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{ai_url}/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "system", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                },
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    return content
    except httpx.RequestError as e:
        log.warning("draft_generator.ai_unreachable", error=str(e))

    return _template_fallback(intent, evidence, category)


def _template_fallback(intent: str, evidence: dict[str, Any], category: str = "default") -> str:
    """Generate a template-based response when AI is unavailable."""
    intent_fallbacks = TEMPLATE_FALLBACKS.get(intent, {})
    if category in intent_fallbacks:
        template = intent_fallbacks[category]
    elif "default" in intent_fallbacks:
        template = intent_fallbacks["default"]
    else:
        return (
            "Thank you for your message. I appreciate your thorough review of this finding. "
            "Please find the relevant evidence attached. I am available to provide any "
            "additional information you may need."
        )

    try:
        return template.format(**evidence)
    except (KeyError, ValueError):
        pass

    return (
        f"Thank you for your message regarding this {category} finding. "
        f"I have prepared the relevant evidence and analysis for your review. "
        f"Please let me know if you need any additional information."
    )
