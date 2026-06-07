"""Cairo ChainAdapter — implements the ABC from vyper_lib.models.chain_adapter."""

from __future__ import annotations

from typing import Any

import structlog

from src.detectors import DETECTOR_REGISTRY, run_detector
from vyper_lib.models.chain_adapter import (
    Chain,
    ChainAdapter,
    CompileResult,
    ContractSource,
    Language,
)

log = structlog.get_logger()


def _parse_cairo_functions(source: str) -> list[dict[str, Any]]:
    """Basic Cairo function extraction from source code."""
    import re
    functions: list[dict[str, Any]] = []
    decorator_pattern = re.compile(r'@(\w+)\s*')
    func_pattern = re.compile(r'func\s+(\w+)\s*\((.*?)\)(?:\s*->\s*\((.*?)\))?\s*[:{]', re.DOTALL)

    for match in func_pattern.finditer(source):
        name = match.group(1)
        params_raw = match.group(2).strip() if match.group(2) else ""
        returns_raw = match.group(3).strip() if match.group(3) else ""

        start = match.start()
        prefix = source[max(0, start - 200):start]
        decorators = [m.group(1) for m in decorator_pattern.finditer(prefix)]

        functions.append({
            "name": name,
            "params": params_raw,
            "returns": returns_raw,
            "decorators": decorators,
            "is_external": "external" in decorators or "view" in decorators,
            "is_view": "view" in decorators,
            "is_constructor": "constructor" in decorators,
            "line": source[:start].count("\n") + 1,
            "body": match.group(0),
        })

    return functions


def _parse_cairo_storage(source: str) -> list[dict[str, Any]]:
    """Detect Cairo storage variable declarations."""
    import re
    storage_vars: list[dict[str, Any]] = []
    storage_pattern = re.compile(
        r'@storage_var\s*\n\s*func\s+(\w+)\s*\((.*?)\)(?:\s*->\s*\(?(.*?)\)?)?\s*[:{]',
        re.DOTALL
    )

    for match in storage_pattern.finditer(source):
        storage_vars.append({
            "name": match.group(1),
            "params": match.group(2).strip() if match.group(2) else "",
            "returns": match.group(3).strip() if match.group(3) else "",
        })

    return storage_vars


def _detect_external_calls(source: str) -> list[dict[str, Any]]:
    """Detect external contract calls in Cairo."""
    import re
    calls: list[dict[str, Any]] = []
    call_pattern = re.compile(r'call_contract\s*\(', re.DOTALL)
    for match in call_pattern.finditer(source):
        calls.append({
            "line": source[:match.start()].count("\n") + 1,
            "call": match.group(0),
        })
    return calls


def _detect_events(source: str) -> list[str]:
    """Detect event emission in Cairo source."""
    import re
    events: list[str] = []
    event_pattern = re.compile(r'@event\s*\n\s*func\s+(\w+)', re.DOTALL)
    for match in event_pattern.finditer(source):
        events.append(match.group(1))
    return events


def _detect_access_checks(source: str, functions: list[dict[str, Any]]) -> dict[str, bool]:
    """Check which external functions have access control."""
    import re
    access_patterns = [
        r'ownable',
        r'access_control',
        r'only_owner',
        r'only_role',
        r'assert_owner',
        r'assert_only_',
        r'get_caller_address',
        r'get_contract_owner',
    ]
    result: dict[str, bool] = {}
    for func in functions:
        if not func["is_external"] and not func["is_constructor"]:
            continue
        name = func["name"]
        body_start = source.find(func["body"])
        body_end = body_start + len(func["body"]) if body_start >= 0 else len(source)
        body = source[body_start:body_end]
        has_check = any(
            re.search(pattern, body, re.IGNORECASE)
            for pattern in access_patterns
        )
        result[name] = has_check
    return result


class CairoAdapter(ChainAdapter):
    chain = Chain.STARKNET
    language = Language.CAIRO

    async def parse(self, source: ContractSource) -> Any:
        all_functions: list[dict[str, Any]] = []
        all_storage: list[dict[str, Any]] = []
        all_events: list[str] = []
        all_calls: list[dict[str, Any]] = []
        full_source = ""

        for _, content in source.source_files.items():
            full_source += content + "\n"

        all_functions = _parse_cairo_functions(full_source)
        all_storage = _parse_cairo_storage(full_source)
        all_events = _detect_events(full_source)
        all_calls = _detect_external_calls(full_source)

        return {
            "contract_name": source.name or "UnknownContract",
            "functions": all_functions,
            "storage_vars": all_storage,
            "events": all_events,
            "external_calls": all_calls,
            "access_checks": _detect_access_checks(full_source, all_functions),
            "source": full_source,
        }

    async def compile(self, source: ContractSource) -> CompileResult:
        return CompileResult(
            success=True,
            bytecode=None,
            abi=None,
            errors=[],
            warnings=[],
            compiler_version="cairo-simulated",
            metadata={"simulated": True, "reason": "Compilation not performed in scanner"},
        )

    async def to_ir(self, parsed_or_compiled: Any, source: ContractSource) -> dict[str, Any]:
        parsed = parsed_or_compiled

        storage_layout: dict[int, dict[str, Any]] = {}
        state_variables: dict[str, dict[str, Any]] = {}
        for i, sv in enumerate(parsed.get("storage_vars", [])):
            slot = i
            storage_layout[slot] = {
                "name": sv.get("name", f"var_{i}"),
                "type": "felt",
                "slot": slot,
            }
            state_variables[sv.get("name", f"var_{i}")] = {
                "name": sv.get("name", f"var_{i}"),
                "type": "felt",
                "visibility": "internal",
            }

        events: dict[str, dict[str, Any]] = {}
        for ev in parsed.get("events", []):
            events[ev] = {"name": ev, "parameters": []}

        functions: dict[str, dict[str, Any]] = {}
        for func in parsed.get("functions", []):
            func_name = func["name"]
            has_access = parsed.get("access_checks", {}).get(func_name, False)
            functions[func_name] = {
                "name": func_name,
                "signature": f"{func_name}({func.get('params', '')})",
                "visibility": "external" if func.get("is_external") else "public",
                "is_view": func.get("is_view", False),
                "is_constructor": func.get("is_constructor", False),
                "has_access_control": has_access,
                "decorators": func.get("decorators", []),
            }

        external_calls: dict[str, list[str]] = {}
        for call in parsed.get("external_calls", []):
            line = call.get("line", 0)
            for func_name in functions:
                func = parsed.get("functions", [])
                for f in func:
                    if f.get("name") == func_name and f.get("line", 0) <= line:
                        external_calls.setdefault(func_name, []).append(
                            f"call_contract@{line}"
                        )
                        break

        ir: dict[str, Any] = {
            "name": parsed.get("contract_name", source.name or "UnknownContract"),
            "chain": "starknet",
            "language": "cairo",
            "address": source.address,
            "compiler_version": source.compiler_version,
            "functions": functions,
            "storage_layout": storage_layout,
            "state_variables": state_variables,
            "events": events,
            "external_calls": external_calls,
            "source": parsed.get("source", ""),
            "_raw_parse": parsed,
        }

        return ir

    async def get_detectors(self) -> list[str]:
        return sorted(DETECTOR_REGISTRY.keys())

    async def analyze(self, ir_contract: dict[str, Any], detectors: list[str]) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        detector_results: dict[str, list[dict[str, Any]]] = {}

        if not detectors:
            detectors = list(DETECTOR_REGISTRY.keys())

        for name in detectors:
            if name not in DETECTOR_REGISTRY:
                continue
            try:
                result = run_detector(name, ir_contract)
                detector_results[name] = result
                findings.extend(result)
            except Exception as exc:
                log.warning("cairo.detector_failed", detector=name, error=str(exc))
                detector_results[name] = []

        return {
            "findings": findings,
            "detector_results": detector_results,
        }
