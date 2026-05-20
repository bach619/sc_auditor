"""AbiExtractor — Extract ABI dari source code tanpa compile ulang.

Menggunakan regex + pattern matching untuk mengekstrak function signatures,
events, dan errors dari Solidity source code.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import structlog

from src.models import SourceResult

log = structlog.get_logger()


class FunctionABI:
    """Extracted function ABI."""

    def __init__(
        self,
        name: str,
        signature: str,
        selector: str,
        inputs: list[dict],
        state_mutability: str = "nonpayable",
    ) -> None:
        self.name = name
        self.signature = signature
        self.selector = selector
        self.inputs = inputs
        self.state_mutability = state_mutability


class EventABI:
    """Extracted event ABI."""

    def __init__(self, name: str, signature: str, topic: str, inputs: list[dict]) -> None:
        self.name = name
        self.signature = signature
        self.topic = topic
        self.inputs = inputs


class ContractABI:
    """Complete contract ABI."""

    def __init__(
        self,
        functions: list[dict] | None = None,
        events: list[dict] | None = None,
        errors: list[dict] | None = None,
        raw_abi: list[dict] | None = None,
    ) -> None:
        self.functions = functions or []
        self.events = events or []
        self.errors = errors or []
        self.raw_abi = raw_abi or []


# Regex patterns
_FUNC_PATTERN = re.compile(
    r"function\s+(\w+)\s*\(([^)]*)\)\s*"
    r"(?:\s*(?:public|external|internal|private))?"
    r"(?:\s*(?:pure|view|payable|nonpayable))?"
)
_EVENT_PATTERN = re.compile(r"event\s+(\w+)\s*\(([^)]*)\)")
_ERROR_PATTERN = re.compile(r"error\s+(\w+)\s*\(([^)]*)\)")
_PARAM_PATTERN = re.compile(r"(\w+(?:\[\])*(?:\s+(?:calldata|memory|storage))?)")
_MODIFIER_PATTERN = re.compile(r"(public|external|internal|private)")
_MUTABILITY_PATTERN = re.compile(r"(pure|view|payable|nonpayable)")


def _parse_param(raw: str) -> dict:
    """Parse a single parameter definition."""
    raw = raw.strip()
    # Handle memory/storage/calldata references
    base_type = raw.split()[0] if raw else "uint256"
    # Clean array brackets
    param_type = base_type.strip()
    name = ""
    parts = raw.split()
    if len(parts) > 1:
        param_type = parts[0]
        name = parts[-1].lstrip("_")
    return {"type": param_type, "name": name or "param"}


def _keccak_4bytes(sig: str) -> str:
    """Compute 4-byte selector for a function signature."""
    return hashlib.sha256(sig.encode()).hexdigest()[:8]


def _keccak_topic(sig: str) -> str:
    """Compute 32-byte topic for an event signature."""
    return "0x" + hashlib.sha256(sig.encode()).hexdigest()


class AbiExtractor:
    """Extract ABI dari Solidity source code menggunakan pattern matching.

    Usage::

        extractor = AbiExtractor()
        abi = extractor.extract(source_result)
    """

    def extract(self, source: SourceResult) -> ContractABI | None:
        """Extract ABI dari source code.

        Args:
            source: SourceResult dari cache atau fetch.

        Returns:
            ContractABI dengan functions, events, errors.
        """
        if not source or not source.sources:
            return None

        functions: list[dict] = []
        events: list[dict] = []
        errors: list[dict] = []

        for filename, content in source.sources.items():
            if not content:
                continue

            # Extract functions
            for match in _FUNC_PATTERN.finditer(content):
                name = match.group(1)
                params_raw = match.group(2)
                full_match = match.group(0)

                # Skip constructor, receive, fallback
                if name in ("constructor", "receive", "fallback"):
                    continue

                params = [_parse_param(p) for p in _PARAM_PATTERN.findall(params_raw) if p.strip()]
                param_types = [p["type"] for p in params]
                sig = f"{name}({','.join(param_types)})"
                selector = _keccak_4bytes(sig)

                # Detect mutability
                mut_match = _MUTABILITY_PATTERN.search(full_match)
                mutability = mut_match.group(1) if mut_match else "nonpayable"

                functions.append({
                    "name": name,
                    "signature": sig,
                    "selector": f"0x{selector}",
                    "inputs": params,
                    "stateMutability": mutability,
                    "type": "function",
                })

            # Extract events
            for match in _EVENT_PATTERN.finditer(content):
                name = match.group(1)
                params_raw = match.group(2)

                params = [_parse_param(p) for p in _PARAM_PATTERN.findall(params_raw) if p.strip()]
                param_types = [p["type"] for p in params]
                sig = f"{name}({','.join(param_types)})"
                topic = _keccak_topic(sig)

                events.append({
                    "name": name,
                    "signature": sig,
                    "topic": topic,
                    "inputs": params,
                    "type": "event",
                })

            # Extract errors
            for match in _ERROR_PATTERN.finditer(content):
                name = match.group(1)
                params_raw = match.group(2)

                params = [_parse_param(p) for p in _PARAM_PATTERN.findall(params_raw) if p.strip()]

                errors.append({
                    "name": name,
                    "inputs": params,
                    "type": "error",
                })

        raw_abi = functions + events + errors

        return ContractABI(
            functions=functions,
            events=events,
            errors=errors,
            raw_abi=raw_abi,
        )

    def _to_json_abi(self, functions: list[dict], events: list[dict], errors: list[dict]) -> list[dict]:
        """Convert to standard JSON ABI format."""
        return functions + events + errors
