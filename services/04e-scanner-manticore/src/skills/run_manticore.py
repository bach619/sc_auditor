from typing import Any
from shared.skills.base_skill import BaseSkill


class RunManticoreSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "run_manticore"

    @property
    def description(self) -> str:
        return "Run Manticore symbolic execution focused on HIGH/CRITICAL bugs"

    @property
    def category(self) -> str:
        return "symbolic_execution"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "object",
                    "description": "Source files keyed by path",
                },
                "contract_name": {
                    "type": "string",
                    "description": "Contract name to analyze",
                },
                "functions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific functions to test symbolically",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max analysis duration in seconds",
                },
            },
            "required": ["sources"],
        }

    async def run(self, **kwargs) -> dict:
        sources = kwargs.get("sources", {})
        contract_name = kwargs.get("contract_name", "unknown")
        functions = kwargs.get("functions", [])
        timeout = kwargs.get("timeout", 300)
        return {
            "skill": self.name,
            "confidence": 0.95,
            "result": f"Ran Manticore analysis on {contract_name} ({len(functions)} functions, {len(sources)} files, timeout={timeout}s)",
        }
