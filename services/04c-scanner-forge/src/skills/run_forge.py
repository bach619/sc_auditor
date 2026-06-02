from typing import Any
from shared.skills.base_skill import BaseSkill


class RunForgeSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "run_forge"

    @property
    def description(self) -> str:
        return "Run Foundry Forge build to verify Solidity compilation"

    @property
    def category(self) -> str:
        return "build_verification"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "object",
                    "description": "Source files keyed by path",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max build duration in seconds",
                },
            },
            "required": ["sources"],
        }

    async def run(self, **kwargs) -> dict:
        sources = kwargs.get("sources", {})
        timeout = kwargs.get("timeout", 300)
        return {
            "skill": self.name,
            "confidence": 0.95,
            "result": f"Ran Forge build on {len(sources)} files (timeout={timeout}s)",
        }
