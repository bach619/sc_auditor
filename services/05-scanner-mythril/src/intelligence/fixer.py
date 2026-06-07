"""Mythril Fix Generator — L4 Intelligence.

Template-based fix suggestions per SWC ID.
Lebih standard dari pada per detector name (seperti 04a) karena
SWC adalah standard industri.
"""

from __future__ import annotations

from typing import Any

SWC_FIXES: dict[str, dict[str, Any]] = {
    "SWC-107": {
        "description": "Reentrancy — external call sebelum state update.",
        "before": "function withdraw(uint256 a) external {\n    (bool s,) = msg.sender.call{value: a}(\"\");\n    require(s);\n    balances[msg.sender] -= a;\n}",
        "after": "function withdraw(uint256 a) external {\n    balances[msg.sender] -= a;\n    (bool s,) = msg.sender.call{value: a}(\"\");\n    require(s);\n}",
        "solidity_example": "// Checks-Effects-Interactions\nbalances[msg.sender] -= amount;\n(bool s,) = msg.sender.call{value: amount}(\"\");\nrequire(s);",
        "references": ["https://swcregistry.io/docs/SWC-107"],
        "confidence": 0.95,
    },
    "SWC-104": {
        "description": "Unchecked return value dari low-level call.",
        "before": "(bool s,) = target.call(data);",
        "after": "(bool s,) = target.call(data);\nrequire(s, \"call failed\");",
        "solidity_example": "(bool success, bytes memory ret) = target.call{value: amount}(\"\");\nrequire(success, \"Call failed\");",
        "references": ["https://swcregistry.io/docs/SWC-104"],
        "confidence": 0.85,
    },
    "SWC-105": {
        "description": "Unprotected ether withdrawal — fungsi withdraw tanpa access control.",
        "before": "function withdrawAll() external {\n    payable(msg.sender).transfer(address(this).balance);\n}",
        "after": "function withdrawAll() external onlyOwner {\n    payable(msg.sender).transfer(address(this).balance);\n}",
        "solidity_example": "modifier onlyOwner() {\n    require(msg.sender == owner, \"Not owner\");\n    _;\n}\n\nfunction withdrawAll() external onlyOwner {\n    payable(msg.sender).transfer(address(this).balance);\n}",
        "references": ["https://swcregistry.io/docs/SWC-105"],
        "confidence": 0.95,
    },
    "SWC-112": {
        "description": "Controlled delegatecall — attacker bisa eksekusi arbitrary code.",
        "before": "function execute(address impl, bytes calldata data) external {\n    (bool s,) = impl.delegatecall(data);\n    require(s);\n}",
        "after": "function execute(address impl, bytes calldata data) external {\n    require(whitelisted[impl], \"not allowed\");\n    (bool s,) = impl.delegatecall(data);\n    require(s);\n}",
        "solidity_example": "mapping(address => bool) public whitelisted;\n\nfunction execute(address impl, bytes calldata data) external {\n    require(whitelisted[impl], \"Unauthorized\");\n    (bool s,) = impl.delegatecall(data);\n    require(s);\n}",
        "references": ["https://swcregistry.io/docs/SWC-112"],
        "confidence": 0.95,
    },
    "SWC-115": {
        "description": "Authorization via tx.origin — phishing risk.",
        "before": "require(tx.origin == owner);",
        "after": "require(msg.sender == owner);",
        "solidity_example": "modifier onlyOwner() {\n    require(msg.sender == owner, \"Not owner\");\n    _;\n}",
        "references": ["https://swcregistry.io/docs/SWC-115"],
        "confidence": 0.95,
    },
    "SWC-101": {
        "description": "Integer overflow — operasi aritmatika tanpa safe check.",
        "before": "function add(uint256 a, uint256 b) pure returns (uint256) {\n    return a + b;\n}",
        "after": "// Solidity 0.8+ built-in overflow check\nfunction add(uint256 a, uint256 b) pure returns (uint256) {\n    return a + b;\n}",
        "solidity_example": "// Gunakan Solidity >=0.8.0 atau SafeMath\nimport \"@openzeppelin/contracts/utils/math/SafeMath.sol\";\nusing SafeMath for uint256;\n\nfunction add(uint256 a, uint256 b) pure returns (uint256) {\n    return a.add(b);\n}",
        "references": ["https://swcregistry.io/docs/SWC-101"],
        "confidence": 0.90,
    },
}


class MythrilFixer:
    """Generate fix suggestions berdasarkan SWC ID."""

    def generate_fix(
        self,
        swc_id: str,
        title: str,
        severity: str,
    ) -> dict[str, Any]:
        template = SWC_FIXES.get(swc_id.upper())
        if template is None:
            return {
                "swc_id": swc_id,
                "title": title,
                "description": f"Review finding: {title}. Refer to SWC documentation.",
                "before": "",
                "after": "",
                "solidity_example": "",
                "references": [f"https://swcregistry.io/docs/{swc_id}"] if swc_id.startswith("SWC-") else [],
                "confidence": 0.4,
            }

        return {
            "swc_id": swc_id,
            "title": title,
            "description": template["description"],
            "before": template.get("before", ""),
            "after": template.get("after", ""),
            "solidity_example": template.get("solidity_example", ""),
            "references": template.get("references", []),
            "confidence": template.get("confidence", 0.7),
        }

    def generate_fixes(
        self,
        findings: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for f in findings:
            swc = f.get("swc_id", "unknown")
            fix = self.generate_fix(
                swc_id=swc,
                title=f.get("title", ""),
                severity=f.get("severity", "medium"),
            )
            result.setdefault(swc, []).append(fix)
        return result

    def get_known_swc(self) -> list[str]:
        return sorted(SWC_FIXES.keys())

    def get_stats(self) -> dict[str, Any]:
        return {"known_swc": len(SWC_FIXES), "swc_ids": sorted(SWC_FIXES.keys())}


def create_fixer() -> MythrilFixer:
    return MythrilFixer()
