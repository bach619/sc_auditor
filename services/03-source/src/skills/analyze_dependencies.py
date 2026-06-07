"""AnalyzeDependenciesSkill — Resolve and analyze contract import dependencies."""

from __future__ import annotations

import re
from typing import Any

import structlog
from shared.skills.base_skill import BaseSkill

log = structlog.get_logger()

_IMPORT_PATTERN = re.compile(r"import\s+(?:{[^}]*}\s+from\s+)?['\"]([^'\"]+)['\"]")

KNOWN_LIBRARIES: dict[str, str] = {
    "openzeppelin": "OpenZeppelin",
    "@openzeppelin": "OpenZeppelin",
    "solmate": "Solmate",
    "forge-std": "Foundry Forge Std",
    "hardhat": "Hardhat",
    "@uniswap": "Uniswap",
    "@aave": "Aave",
    "@chainlink": "Chainlink",
}


class AnalyzeDependenciesSkill(BaseSkill):
    """Analyzes import dependencies in Solidity source code.

    Parses all source files for import statements, resolves known libraries,
    and builds a dependency graph showing the relationships between contracts.
    """

    @property
    def name(self) -> str:
        return "analyze_dependencies"

    @property
    def description(self) -> str:
        return (
            "Analyze import dependencies across all source files. "
            "Builds a dependency graph, resolves known libraries (OpenZeppelin, "
            "Solmate, Uniswap, etc.), detects circular dependencies, and "
            "identifies external vs internal imports."
        )

    @property
    def category(self) -> str:
        return "source_intel"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "object",
                    "description": "Dictionary mapping file paths to source code strings",
                    "additionalProperties": {"type": "string"},
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum recursion depth for dependency resolution",
                    "default": 3,
                },
            },
            "required": ["sources"],
        }

    async def run(self, sources: dict[str, str], **kwargs: Any) -> dict[str, Any]:
        max_depth = kwargs.get("max_depth", 3)
        log.info("analyze_dependencies_skill", file_count=len(sources), max_depth=max_depth)

        imports: dict[str, list[str]] = {}
        library_refs: list[str] = []
        externals: list[str] = []
        internal_deps: dict[str, list[str]] = {}

        for filepath, content in sources.items():
            found = _IMPORT_PATTERN.findall(content)
            imports[filepath] = found
            for imp in found:
                if any(lib in imp for lib in KNOWN_LIBRARIES):
                    library = next(
                        (KNOWN_LIBRARIES[lib] for lib in KNOWN_LIBRARIES if lib in imp),
                        "Unknown",
                    )
                    library_refs.append(library)
                elif imp.startswith(".") or imp.startswith("contracts/"):
                    if filepath not in internal_deps:
                        internal_deps[filepath] = []
                    internal_deps[filepath].append(imp)
                else:
                    externals.append(imp)

        total_imports = sum(len(v) for v in imports.values())
        circular = self._detect_circular(internal_deps)

        dep_tree = self._build_tree(imports)

        return {
            "total_files": len(sources),
            "total_imports": total_imports,
            "imports_per_file": {k: len(v) for k, v in imports.items()},
            "dependency_tree": dep_tree,
            "internal_dependencies": internal_deps,
            "external_imports": list(set(externals)),
            "library_references": list(set(library_refs)),
            "circular_dependencies": circular,
            "max_depth": max_depth,
        }

    def _detect_circular(self, deps: dict[str, list[str]]) -> list[list[str]]:
        """Simple cycle detection in the dependency graph."""
        cycles: list[list[str]] = []
        visited: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> None:
            if node in path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            for dep in deps.get(node, []):
                dfs(dep)
            path.pop()

        for node in deps:
            dfs(node)

        return cycles

    def _build_tree(self, imports: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        tree: dict[str, dict[str, Any]] = {}
        for filepath, deps in imports.items():
            tree[filepath] = {
                "imports": deps,
                "count": len(deps),
            }
        return tree
