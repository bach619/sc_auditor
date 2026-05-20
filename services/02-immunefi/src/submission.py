"""ImmunefiSubmissionBot — Auto-submit finding ke Immunefi API.

Membutuhkan IMMUNEFI_API_KEY dengan scope submission.
Semua submission dilacak di indexes/submissions.json.

Flow:
  1. Validasi finding (duplicate check, severity, reproducibility)
  2. Submit via POST /v1/submissions
  3. Track submission status (pending/accepted/rejected)
  4. Alert kalau ada perubahan status
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from src.storage import EnhancedJSONStorage

log = structlog.get_logger()

IMMUNEFI_API_BASE = "https://api.immunefi.com/v1"


class ImmunefiSubmissionBot:
    """Submit finding ke Immunefi dan track statusnya.

    Usage:
        bot = ImmunefiSubmissionBot(storage)
        result = await bot.submit(
            program_slug="euler-finance",
            title="Reentrancy in withdraw()",
            description="...",
            severity="critical",
            vulnerability_classification="reentrancy",
            proof_of_concept="...",
            contract_address="0x...",
        )
    """

    def __init__(
        self,
        storage: EnhancedJSONStorage,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.storage = storage
        self._client = client

    def _get_api_key(self) -> str | None:
        return os.getenv("IMMUNEFI_API_KEY")

    def is_available(self) -> bool:
        return self._get_api_key() is not None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    # ── Submission Tracking ─────────────────────────────────

    def _get_submissions(self) -> dict[str, Any]:
        data = self.storage.get_index("submissions")
        return data if isinstance(data, dict) else {}

    def _save_submissions(self, submissions: dict) -> None:
        try:
            import json  # noqa: PLC0415
            path = self.storage.data_dir / "indexes" / "submissions.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(submissions, indent=2))
        except Exception as e:
            log.warning("submission.save_error", error=str(e)[:100])

    # ── Validation ─────────────────────────────────────────

    async def validate_finding(
        self,
        title: str,
        severity: str,
        description: str,
        contract_address: str,
    ) -> dict[str, Any]:
        """Validasi finding sebelum submit."""
        checks = []
        passed = True

        # Severity check
        valid_severities = {"critical", "high", "medium", "low", "informational"}
        severity_ok = severity.lower() in valid_severities
        checks.append({
            "check": "severity",
            "passed": severity_ok,
            "message": f"Severity must be one of: {valid_severities}" if not severity_ok else "ok",
        })
        if not severity_ok:
            passed = False

        # Title check
        title_ok = bool(title and len(title) >= 10)
        checks.append({
            "check": "title",
            "passed": title_ok,
            "message": "Title must be at least 10 characters" if not title_ok else "ok",
        })
        if not title_ok:
            passed = False

        # Description check
        desc_ok = bool(description and len(description) >= 50)
        checks.append({
            "check": "description",
            "passed": desc_ok,
            "message": "Description must be at least 50 characters" if not desc_ok else "ok",
        })
        if not desc_ok:
            passed = False

        # Contract address check
        addr_ok = bool(contract_address and contract_address.startswith("0x"))
        checks.append({
            "check": "contract_address",
            "passed": addr_ok,
            "message": "Address must be 0x-prefixed" if not addr_ok else "ok",
        })
        if not addr_ok:
            passed = False

        # Duplicate check (dari submission history)
        submissions = self._get_submissions()
        duplicate = False
        for sub_id, sub in submissions.items():
            if isinstance(sub, dict):
                existing_title = sub.get("title", "").lower().strip()
                if existing_title == title.lower().strip() and sub.get("status") != "rejected":
                    duplicate = True
                    break
        checks.append({
            "check": "duplicate",
            "passed": not duplicate,
            "message": "Duplicate submission — similar title already submitted" if duplicate else "ok",
        })
        if duplicate:
            passed = False

        return {
            "passed": passed,
            "checks": checks,
        }

    # ── Submit ─────────────────────────────────────────────

    async def submit(
        self,
        program_slug: str,
        title: str,
        description: str,
        severity: str,
        vulnerability_classification: str,
        proof_of_concept: str,
        contract_address: str,
        affected_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """Submit finding ke Immunefi API.

        Returns dict dengan status submission.
        """
        api_key = self._get_api_key()
        if not api_key:
            return {
                "status": "failed",
                "error": "IMMUNEFI_API_KEY not set",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # 1. Validate
        validation = await self.validate_finding(
            title=title,
            severity=severity,
            description=description,
            contract_address=contract_address,
        )
        if not validation["passed"]:
            return {
                "status": "validation_failed",
                "checks": validation["checks"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # 2. Prepare submission payload
        submission_id = uuid.uuid4().hex[:12]
        payload = {
            "program": program_slug,
            "title": title,
            "description": description,
            "severity": severity.lower(),
            "vulnerability_classification": vulnerability_classification,
            "proof_of_concept": proof_of_concept,
            "affected_urls": affected_urls or [
                f"https://etherscan.io/address/{contract_address}",
            ],
            "assets": [
                {
                    "type": "contract",
                    "address": contract_address,
                },
            ],
        }

        # 3. Submit via API
        client = await self._get_client()
        log.info(
            "submission.submit.start",
            program=program_slug,
            title=title[:50],
            submission_id=submission_id,
        )

        try:
            resp = await client.post(
                f"{IMMUNEFI_API_BASE}/submissions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

            now = datetime.now(timezone.utc).isoformat()
            submission_record = {
                "submission_id": submission_id,
                "program_slug": program_slug,
                "title": title,
                "severity": severity,
                "vulnerability_classification": vulnerability_classification,
                "created_at": now,
                "status": "pending",
            }

            if resp.status_code == 201:
                data = resp.json()
                submission_record["status"] = "accepted"
                submission_record["immunefi_id"] = data.get("id", "")
                submission_record["response"] = data
                log.info(
                    "submission.submit.success",
                    submission_id=submission_id,
                    immunefi_id=data.get("id"),
                )
                result_status = "submitted"

            elif resp.status_code == 401:
                submission_record["status"] = "failed"
                submission_record["error"] = "API key invalid"
                result_status = "auth_failed"

            elif resp.status_code == 422:
                submission_record["status"] = "failed"
                submission_record["error"] = resp.text[:500]
                result_status = "validation_error"

            else:
                resp.raise_for_status()
                submission_record["status"] = "failed"
                submission_record["error"] = f"HTTP {resp.status_code}"
                result_status = "error"

        except httpx.HTTPStatusError as e:
            now = datetime.now(timezone.utc).isoformat()
            submission_record = {
                "submission_id": submission_id,
                "program_slug": program_slug,
                "title": title,
                "severity": severity,
                "created_at": now,
                "status": "failed",
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
            result_status = "error"

        except Exception as e:
            now = datetime.now(timezone.utc).isoformat()
            submission_record = {
                "submission_id": submission_id,
                "program_slug": program_slug,
                "title": title,
                "severity": severity,
                "created_at": now,
                "status": "failed",
                "error": str(e)[:200],
            }
            result_status = "error"

        # 4. Save to tracking
        submissions = self._get_submissions()
        submissions[submission_id] = submission_record
        self._save_submissions(submissions)

        return {
            "status": result_status,
            "submission_id": submission_id,
            "record": submission_record,
        }

    # ── Query ──────────────────────────────────────────────

    def list_submissions(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List semua submission, optional filter by status."""
        submissions = self._get_submissions()
        results = list(submissions.values())

        if status:
            results = [s for s in results if isinstance(s, dict) and s.get("status") == status]

        # Sort newest first
        results.sort(
            key=lambda x: x.get("created_at", "") if isinstance(x, dict) else "",
            reverse=True,
        )
        return results[:limit]

    def get_submission(self, submission_id: str) -> dict[str, Any] | None:
        """Get detail satu submission."""
        submissions = self._get_submissions()
        entry = submissions.get(submission_id)
        if isinstance(entry, dict):
            return entry
        return None

    def get_stats(self) -> dict[str, Any]:
        """Get submission statistics."""
        submissions = self._get_submissions()
        total = len(submissions)
        by_status: dict[str, int] = {}
        by_program: dict[str, int] = {}

        for s in submissions.values():
            if isinstance(s, dict):
                st = s.get("status", "unknown")
                by_status[st] = by_status.get(st, 0) + 1
                prog = s.get("program_slug", "unknown")
                by_program[prog] = by_program.get(prog, 0) + 1

        return {
            "total_submissions": total,
            "by_status": by_status,
            "by_program": by_program,
        }

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
