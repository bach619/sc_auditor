"""RunMythrilDeepSkill — deep guided analysis pipeline."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class RunMythrilDeepSkill(BaseSkill):
    """Deep Mythril analysis: Slither-guided → Mythril custom plugins → cross-ref → AI."""

    @property
    def name(self) -> str:
        return "run_mythril_deep"

    @property
    def description(self) -> str:
        return (
            "Deep Mythril analysis pipeline: Slither-guided → Mythril custom plugins → "
            "cross-reference with Manticore/Slither/Echidna → AI explanation. "
            "Focused on HIGH/CRITICAL bug confirmation."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "object",
                    "description": "Source files keyed by path",
                },
                "functions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific functions to analyze (optional)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max duration in seconds",
                },
                "depth": {
                    "type": "integer",
                    "description": "Mythril analysis depth (default 42)",
                },
                "use_slither_guide": {
                    "type": "boolean",
                    "description": "Guide analysis with Slither output",
                },
                "use_custom_plugins": {
                    "type": "boolean",
                    "description": "Use custom Mythril modules",
                },
            },
            "required": ["sources"],
        }

    @property
    def category(self) -> str:
        return "scanning"

    async def run(
        self,
        sources: dict[str, str],
        functions: list[str] | None = None,
        timeout: int = 300,
        depth: int = 42,
        use_slither_guide: bool = True,
        use_custom_plugins: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not sources:
            raise ValueError("At least one source file is required")

        # Delegate to GuidedAnalyzer if available
        from ..guided_analyzer import GuidedAnalyzer

        analyzer = GuidedAnalyzer()
        result = await analyzer.analyze(
            source_files=sources,
            functions_to_test=functions,
            timeout=timeout,
            depth=depth,
            use_slither_guide=use_slither_guide,
            use_custom_plugins=use_custom_plugins,
        )
        return result
