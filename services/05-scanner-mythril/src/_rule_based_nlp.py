"""Rule-based NLP engine — fallback when AI is unavailable.

Enhanced version of the original MythrilNLP with:
  - More intent patterns
  - Better finding explanations
  - Severity-aware summaries
  - PoC description generation
"""

from __future__ import annotations

import re
from typing import Any


class _RuleBasedNLP:
    """Rule-based natural language engine for Mythril findings."""

    def explain_finding(self, finding: dict[str, Any]) -> str:
        """Generate human-readable explanation for a single finding."""
        title = finding.get("title", "")
        swc_id = finding.get("swc_id", "")
        severity = finding.get("severity", "medium")
        bug_type = finding.get("bug_type", "")

        explanation = f"[{severity.upper()}] {title}"

        if swc_id:
            explanation += f"\nSWC ID: {swc_id}"

        if bug_type:
            explanation += f"\nType: {bug_type.replace('_', ' ').title()}"

        explanation += "\n\n"

        # Add specific explanation based on bug type
        explanations = {
            "reentrancy": (
                "This function makes an external call before updating its own state. "
                "An attacker can call back into this function recursively, draining "
                "funds before the balance is updated."
            ),
            "cei_violation": (
                "The contract violates the Checks-Effects-Interactions pattern. "
                "State changes should happen BEFORE external calls, not after."
            ),
            "cross_contract_reentrancy": (
                "A cross-contract reentrancy path was detected. Multiple contracts "
                "interact in a way that allows recursive calls across contract boundaries."
            ),
            "access_control": (
                "This function performs sensitive operations without verifying "
                "the caller's identity. Anyone can call this function."
            ),
            "missing_access_control": (
                "No access control mechanism found on a sensitive function. "
                "Consider adding an onlyOwner or role-based modifier."
            ),
            "unprotected_initializer": (
                "The contract initializer has no access control. An attacker can "
                "front-run the deployer and take ownership of the contract."
            ),
            "tx_origin_misuse": (
                "The contract uses tx.origin for authentication. This is dangerous "
                "because tx.origin can be different from msg.sender when called "
                "through another contract."
            ),
            "oracle_manipulation": (
                "The contract uses a spot price oracle that can be manipulated "
                "within a single transaction, especially with flash loans."
            ),
            "flash_loan": (
                "The contract's price oracle does not use TWAP (Time-Weighted "
                "Average Price), making it vulnerable to flash loan attacks."
            ),
            "overflow": (
                "Arithmetic operation can overflow/underflow. In Solidity <0.8, "
                "this wraps around silently. Even in 0.8+, chained operations "
                "can produce unexpected results."
            ),
            "delegatecall": (
                "The contract uses delegatecall, which executes code in its own "
                "storage context. If the target is controllable, an attacker can "
                "execute arbitrary code."
            ),
            "arbitrary_delegatecall": (
                "CRITICAL: The delegatecall target is user-controlled. An attacker "
                "can execute arbitrary code in the contract's context."
            ),
            "unchecked_call": (
                "The return value of an external call is not checked. If the call "
                "fails, the contract continues execution as if it succeeded."
            ),
        }

        for key, text in explanations.items():
            if key in bug_type.lower() or key in title.lower():
                explanation += text
                break
        else:
            explanation += (
                "This vulnerability was detected through symbolic execution. "
                "Review the function logic and ensure proper security measures are in place."
            )

        return explanation

    def generate_report_section(self, findings: list[dict[str, Any]], section: str) -> str:
        """Generate audit report section from findings."""
        if not findings:
            return "No findings to report."

        if section == "summary":
            critical = sum(1 for f in findings if f.get("severity") == "critical")
            high = sum(1 for f in findings if f.get("severity") == "high")
            medium = sum(1 for f in findings if f.get("severity") == "medium")

            return (
                f"Mythril analysis found {len(findings)} potential vulnerabilities: "
                f"{critical} CRITICAL, {high} HIGH, {medium} MEDIUM. "
                f"Critical issues include access control bypass, reentrancy, "
                f"and arbitrary delegatecall patterns that require immediate attention."
            )

        elif section == "detailed":
            lines = ["# Detailed Findings\n"]
            for i, f in enumerate(findings, 1):
                lines.append(f"## {i}. [{f.get('severity', 'info').upper()}] {f.get('title', '')}")
                lines.append(f"\n{f.get('description', '')}\n")
                if f.get("function"):
                    lines.append(f"- **Function**: `{f['function']}`")
                if f.get("swc_id"):
                    lines.append(f"- **SWC**: {f['swc_id']}")
                lines.append("")
            return "\n".join(lines)

        elif section == "recommendations":
            recs = []
            for f in findings:
                severity = f.get("severity", "medium")
                bug_type = f.get("bug_type", "")
                title = f.get("title", "")

                if severity == "critical":
                    recs.append(f"🔴 **CRITICAL**: {title} — Fix immediately before deployment.")
                elif severity == "high":
                    recs.append(f"🟠 **HIGH**: {title} — Address before production.")
                else:
                    recs.append(f"🟡 **MEDIUM**: {title} — Review and address.")

            return "\n".join(recs[:10])

        return "Unknown report section."

    def ask_question(self, question: str, context: dict[str, Any]) -> str:
        """Answer natural language question about findings."""
        q = question.lower()
        findings = context.get("findings", [])
        swc_registry = context.get("swc_registry", {})

        # Summary intent
        if any(w in q for w in ["summary", "overview", "overall", "result"]):
            return self.generate_report_section(findings, "summary")

        # Critical/count intent
        if any(w in q for w in ["critical", "dangerous", "severe", "worst"]):
            crit = [f for f in findings if f.get("severity") == "critical"]
            if crit:
                return f"There are {len(crit)} critical findings:\n" + "\n".join(
                    f"- {f.get('title', '')}" for f in crit
                )
            return "No critical findings detected."

        # Fix intent
        if any(w in q for w in ["fix", "repair", "solve", "how to", "patch"]):
            bug_types = set(f.get("bug_type", "") for f in findings)
            fixes = []
            for bt in bug_types:
                if "reentrancy" in bt:
                    fixes.append("- Use Checks-Effects-Interactions pattern")
                elif "access" in bt:
                    fixes.append("- Add onlyOwner modifier or role-based access control")
                elif "delegatecall" in bt:
                    fixes.append("- Use a whitelist for delegatecall targets")
                elif "overflow" in bt:
                    fixes.append("- Use SafeMath or Solidity 0.8+ built-in overflow protection")
            if fixes:
                return "Suggested fixes:\n" + "\n".join(fixes)
            return "No specific fix suggestions available for these findings."

        # SWC intent
        if "swc" in q:
            swcs = set(f.get("swc_id", "") for f in findings if f.get("swc_id"))
            if swcs:
                return f"SWC IDs involved: {', '.join(sorted(swcs))}"
            return "No SWC references available."

        # Specific vulnerability questions
        vuln_map: dict[str, str] = {
            "reentrancy": "Reentrancy allows recursive calls that drain funds before state updates.",
            "delegatecall": "Delegatecall executes code in the caller's storage context.",
            "overflow": "Integer overflow/underflow causes incorrect arithmetic results.",
            "access control": "Missing access control lets anyone call privileged functions.",
            "oracle": "Oracle manipulation uses flash loans to corrupt price feeds.",
            "tx.origin": "tx.origin auth is bypassable via intermediate contracts.",
        }
        for keyword, explanation in vuln_map.items():
            if keyword in q:
                findings_with_keyword = [
                    f for f in findings
                    if keyword in f.get("bug_type", "").lower()
                    or keyword in f.get("title", "").lower()
                ]
                if findings_with_keyword:
                    return f"{explanation}\n\nAffected functions: " + ", ".join(
                        f"`{f.get('function', 'unknown')}`" for f in findings_with_keyword
                    )
                return f"{explanation}\n\nNo specific findings match this pattern in the current analysis."

        return "I can answer questions about: summary, critical findings, fixes, SWC IDs, and specific vulnerability types."

    def generate_poc_description(self, finding: dict[str, Any]) -> str:
        """Generate a plain-English PoC description."""
        title = finding.get("title", "")
        bug_type = finding.get("bug_type", "")
        function = finding.get("function", "unknown")

        poc_templates: dict[str, str] = {
            "reentrancy": (
                f"**PoC for: {title}**\n\n"
                f"1. Attacker deploys a malicious contract\n"
                f"2. Calls {function}() on the vulnerable contract\n"
                f"3. In the fallback function, calls {function}() again\n"
                f"4. Repeats until funds are drained\n"
                f"5. The contract's balance tracking is never updated correctly"
            ),
            "access_control": (
                f"**PoC for: {title}**\n\n"
                f"1. Call {function}() from any address (not the owner)\n"
                f"2. Observe that the call succeeds\n"
                f"3. Sensitive state is modified without authorization"
            ),
            "delegatecall": (
                f"**PoC for: {title}**\n\n"
                f"1. Deploy a malicious implementation contract\n"
                f"2. Call the vulnerable function with the malicious address\n"
                f"3. The malicious code executes in the proxy's storage context\n"
                f"4. Attacker gains full control of the contract"
            ),
            "overflow": (
                f"**PoC for: {title}**\n\n"
                f"1. Identify the overflow point in {function}()\n"
                f"2. Craft input that causes the arithmetic to wrap\n"
                f"3. The incorrect result bypasses balance checks\n"
                f"4. Attacker extracts more value than intended"
            ),
            "oracle": (
                f"**PoC for: {title}**\n\n"
                f"1. Take a flash loan of the liquidity token\n"
                f"2. Perform a large swap to manipulate the pool price\n"
                f"3. Call {function}() which reads the manipulated price\n"
                f"4. Profit from the price discrepancy\n"
                f"5. Repay the flash loan"
            ),
        }

        for key, template in poc_templates.items():
            if key in bug_type.lower() or key in title.lower():
                return template

        return (
            f"**PoC for: {title}**\n\n"
            f"1. Analyze the vulnerable function {function}()\n"
            f"2. Craft calldata that triggers the vulnerability path\n"
            f"3. Execute the transaction and observe the unexpected behavior\n"
            f"4. Develop an exploit that maximizes the impact"
        )

    def summarize_findings(self, findings: list[dict[str, Any]]) -> str:
        """One-paragraph summary of all findings."""
        if not findings:
            return "No vulnerabilities found."

        critical = sum(1 for f in findings if f.get("severity") == "critical")
        high = sum(1 for f in findings if f.get("severity") == "high")
        total = len(findings)

        bug_types = set()
        for f in findings:
            bt = f.get("bug_type", "")
            if bt:
                bug_types.add(bt.replace("_", " ").title())

        summary = (
            f"Mythril analysis identified {total} potential vulnerabilities "
            f"({critical} critical, {high} high). "
        )

        if bug_types:
            summary += f"The findings span: {', '.join(sorted(bug_types))}. "

        if critical > 0:
            summary += "Immediate action is required for critical findings."

        return summary
