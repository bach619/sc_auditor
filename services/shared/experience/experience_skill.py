"""ExperienceSkill — skill untuk query dan belajar dari pengalaman audit.

Setiap agent memiliki skill ini untuk:
  - Mencari task serupa yang pernah dikerjakan
  - Melihat apa yang gagal sebelumnya
  - Mendapatkan rekomendasi berdasarkan pengalaman
  - Melihat statistik capability mereka
"""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class ExperienceSkill(BaseSkill):
    """Query dan belajar dari pengalaman audit masa lalu.

    Agent bisa mencari task serupa, melihat failure patterns,
    dan mendapatkan insight dari experiencenya sendiri.
    """

    def __init__(self, manager: Any = None) -> None:
        """Initialize dengan ExperienceManager instance.

        Args:
            manager: ExperienceManager instance (di-set oleh agent owner)
        """
        self._manager = manager

    @property
    def name(self) -> str:
        return "experience"

    @property
    def description(self) -> str:
        return (
            "Mencari dan menganalisis pengalaman audit masa lalu. "
            "Berguna untuk: (1) mencari task serupa sebelum mengerjakan task baru, "
            "(2) belajar dari kegagalan sebelumnya, "
            "(3) melihat statistik capability sendiri, "
            "(4) mendapatkan rekomendasi berdasarkan pengalaman. "
            "Semakin banyak pengalaman, semakin pintar agent."
        )

    @property
    def category(self) -> str:
        return "experience"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "find_similar",
                        "find_failures",
                        "find_successes",
                        "get_stats",
                        "get_success_rate",
                        "get_finding_type_stats",
                        "get_consolidations",
                        "consolidate",
                        "recent",
                        "advice",
                    ],
                    "description": "Aksi yang diminta",
                },
                "capability": {
                    "type": "string",
                    "description": "Filter by capability name",
                },
                "contract_name": {
                    "type": "string",
                    "description": "Filter by contract name",
                },
                "chain": {
                    "type": "string",
                    "description": "Filter by blockchain",
                },
                "finding_type": {
                    "type": "string",
                    "description": "Filter by finding type (reentrancy, access_control, dll)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default: 10)",
                },
            },
            "required": ["action"],
        }

    def set_manager(self, manager: Any) -> None:
        """Set ExperienceManager setelah konstruksi."""
        self._manager = manager

    async def run(
        self,
        action: str = "get_stats",
        capability: str | None = None,
        contract_name: str = "",
        chain: str = "",
        finding_type: str = "",
        limit: int = 10,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if self._manager is None:
            return {
                "skill": "experience",
                "action": action,
                "error": "ExperienceManager not initialized",
                "available": False,
            }

        result: dict[str, Any] = {
            "skill": "experience",
            "action": action,
            "confidence": 0.95,
            "agent": self._manager._agent_service,
        }

        if action == "find_similar":
            exps = self._manager.find_similar_tasks(
                capability=capability or "",
                contract_name=contract_name,
                chain=chain,
                limit=limit,
            )
            result["experiences"] = [e.to_dict() for e in exps]
            result["total"] = len(exps)

        elif action == "find_failures":
            exps = self._manager.find_failures(
                capability=capability, limit=limit
            )
            result["experiences"] = [e.to_dict() for e in exps]
            result["total"] = len(exps)
            result["lesson"] = self._extract_lesson(exps)

        elif action == "find_successes":
            exps = self._manager.find_successes(
                capability=capability or "", limit=limit
            )
            result["experiences"] = [e.to_dict() for e in exps]
            result["total"] = len(exps)

        elif action == "get_stats":
            result["stats"] = self._manager.get_stats()
            result["success_rate"] = self._manager.get_success_rate(capability)

        elif action == "get_success_rate":
            result["success_rate"] = self._manager.get_success_rate(capability)
            result["total_tasks"] = self._manager.store.count(
                agent_service=self._manager._agent_service,
                capability=capability,
            )

        elif action == "get_finding_type_stats":
            result["finding_type_stats"] = self._manager.store.get_finding_type_stats(
                agent_service=self._manager._agent_service,
            )

        elif action == "get_consolidations":
            result["consolidations"] = self._manager.get_consolidations()

        elif action == "consolidate":
            new_cons = self._manager.consolidate()
            result["new_consolidations"] = [c.to_dict() for c in new_cons]
            result["total"] = len(new_cons)

        elif action == "recent":
            exps = self._manager.store.get_recent(limit=limit)
            result["experiences"] = [e.to_dict() for e in exps]
            result["total"] = len(exps)

        elif action == "advice":
            result["advice"] = self._generate_advice(capability, contract_name, chain, finding_type)

        else:
            return {
                "skill": "experience",
                "action": action,
                "error": f"Unknown action: {action}",
            }

        return result

    def _extract_lesson(self, failures: list) -> str:
        """Extract pelajaran dari failures."""
        if not failures:
            return "No failures recorded yet — clean record!"

        total = len(failures)
        by_capability: dict[str, int] = {}
        by_finding: dict[str, int] = {}
        for f in failures:
            by_capability[f.capability] = by_capability.get(f.capability, 0) + 1
            for ft in f.finding_types:
                by_finding[ft] = by_finding.get(ft, 0) + 1

        top_cap = max(by_capability, key=by_capability.get) if by_capability else "unknown"
        top_finding = max(by_finding, key=by_finding.get) if by_finding else "unknown"

        return (
            f"From {total} failures: most failures in '{top_cap}' capability, "
            f"most common finding type: '{top_finding}'. "
            f"Review detection logic for {top_finding} in {top_cap}."
        )

    def _generate_advice(
        self,
        capability: str | None,
        contract_name: str,
        chain: str,
        finding_type: str,
    ) -> str:
        """Generate advice sebelum agent mulai task baru."""
        parts = []

        # Cek failures in this capability
        failures = self._manager.store.count(
            agent_service=self._manager._agent_service,
            capability=capability,
            success=False,
        )
        if failures > 0:
            parts.append(
                f"⚠️  Warning: {failures} previous failure(s) for capability "
                f"'{capability}'. Past learnings: check similar previous tasks."
            )

        # Cek success rate
        rate = self._manager.get_success_rate(capability)
        if rate < 0.5 and failures > 0:
            parts.append(
                f"📉 Low success rate ({rate:.0%}) for this capability. "
                f"Consider extra validation."
            )

        # Cek total pengalaman
        total = self._manager.store.count(
            agent_service=self._manager._agent_service,
        )
        if total > 0:
            parts.append(f"📚 Total experiences: {total} audit task(s) recorded.")

        if not parts:
            parts.append("✅ No relevant past experiences — this is a new frontier!")

        return " | ".join(parts)
