"""Resilient pipeline step with retry, fallback, and criticality."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger("vyper.orchestrator.pipeline.resilient")


class StepStatus:
    SUCCESS = "success"
    DEGRADED = "degraded"
    SKIPPED = "skipped"
    FAILED = "failed"


class ResilientPipelineStep:
    """A pipeline step with retry, fallback, and criticality.

    Usage:
        step = ResilientPipelineStep("scan", max_retries=3, critical=True)
        result = await step.execute(context, actual_handler)
    """

    def __init__(
        self,
        name: str,
        max_retries: int = 3,
        fallback_fn=None,
        critical: bool = True,
    ) -> None:
        self.name = name
        self.max_retries = max_retries
        self.fallback_fn = fallback_fn
        self.critical = critical

    async def execute(self, context: dict, handler) -> dict:
        """Execute step with retry + fallback logic.

        Args:
            context: Pipeline context dict
            handler: Async callable that does the actual work

        Returns:
            dict with keys: status ("success"|"degraded"|"skipped"), data, error
        """
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 2):
            try:
                result = await handler(context)
                return {"status": "success", "data": result}
            except Exception as e:
                last_error = e
                if attempt <= self.max_retries:
                    wait = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        "Step %s retry %d/%d in %ds: %s",
                        self.name, attempt, self.max_retries, wait, e,
                    )
                    await asyncio.sleep(wait)

        # All retries exhausted
        if self.fallback_fn is not None:
            logger.info("Step %s using fallback", self.name)
            try:
                fallback = await self.fallback_fn(context)
                return {
                    "status": "degraded",
                    "data": fallback,
                    "error": str(last_error),
                }
            except Exception as fb_err:
                last_error = fb_err

        if self.critical:
            raise RuntimeError(
                f"Critical step '{self.name}' failed after "
                f"{self.max_retries + 1} attempts: {last_error}"
            )

        logger.warning("Step %s skipped (non-critical): %s", self.name, last_error)
        return {"status": "skipped", "error": str(last_error)}


__all__ = ["ResilientPipelineStep", "StepStatus"]
