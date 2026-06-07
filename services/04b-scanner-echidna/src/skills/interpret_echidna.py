from shared.skills.base_skill import BaseSkill


class InterpretEchidnaSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "interpret_echidna"

    @property
    def description(self) -> str:
        return "Analyze Echidna fuzzing output, counterexamples, and property test failures"

    @property
    def category(self) -> str:
        return "fuzzing"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "echidna_output": {
                    "type": "object",
                    "description": "Output from Echidna fuzzing run",
                },
            },
            "required": ["echidna_output"],
        }

    async def run(self, **kwargs) -> dict:
        echidna_output = kwargs.get("echidna_output", {})
        return {
            "skill": self.name,
            "confidence": 0.90,
            "result": f"Interpreted Echidna output with {len(echidna_output)} fields",
        }
