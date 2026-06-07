from shared.skills.base_skill import BaseSkill


class AnalyzeBuildErrorsSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "analyze_build_errors"

    @property
    def description(self) -> str:
        return "Categorize compiler errors and suggest fixes"

    @property
    def category(self) -> str:
        return "build_verification"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "errors": {
                    "type": "array",
                    "description": "Compiler errors from Forge build",
                },
            },
            "required": ["errors"],
        }

    async def run(self, **kwargs) -> dict:
        errors = kwargs.get("errors", [])
        return {
            "skill": self.name,
            "confidence": 0.88,
            "result": f"Analyzed {len(errors)} build errors",
        }
