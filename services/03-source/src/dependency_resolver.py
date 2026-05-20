"""DependencyResolver — Resolve import dependencies untuk kontrak.

Menganalisis import statements di source code dan mencoba resolve
ke kontrak yang sudah di-cache atau dikenal (OpenZeppelin, dll).
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from src.storage import EnhancedJSONStorage

log = structlog.get_logger()

_IMPORT_PATTERN = re.compile(r"import\s+(?:{[^}]*}\s+from\s+)?['\"]([^'\"]+)['\"]")

# Known contract mappings (OpenZeppelin, Solmate, etc.)
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


class DependencyResolver:
    """Resolve semua dependencies (imports) untuk satu kontrak.

    Usage::

        resolver = DependencyResolver(storage)
        graph = await resolver.resolve("ethereum", "0x...")
    """

    def __init__(self, storage: EnhancedJSONStorage) -> None:
        self.storage = storage

    async def resolve(
        self,
        chain: str,
        address: str,
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """Resolve semua dependency secara rekursif.

        Args:
            chain: Blockchain name.
            address: Contract address.
            max_depth: Maximum recursion depth.

        Returns:
            Dict dengan dependency graph.
        """
        chain_l = chain.lower()
        addr_l = address.lower()

        graph: dict[str, Any] = {
            "root": f"{chain_l}:{addr_l}",
            "nodes": {},
            "edges": [],
            "total_dependencies": 0,
            "max_depth": max_depth,
        }

        await self._resolve_recursive(chain_l, addr_l, graph, depth=0, max_depth=max_depth)

        graph["total_dependencies"] = len(graph["nodes"]) - 1  # exclude root
        return graph

    async def _resolve_recursive(
        self,
        chain: str,
        address: str,
        graph: dict,
        depth: int,
        max_depth: int,
    ) -> None:
        """Recursive dependency resolution."""
        if depth > max_depth:
            return

        node_key = f"{chain}:{address}"
        if node_key in graph["nodes"]:
            return  # Already resolved

        source = self.storage.get_source(chain, address)
        if not source:
            graph["nodes"][node_key] = {
                "chain": chain,
                "address": address,
                "status": "not_cached",
                "depth": depth,
            }
            return

        # Extract imports
        imports: list[str] = []
        for content in source.sources.values():
            imports.extend(_IMPORT_PATTERN.findall(content))

        # Deduplicate
        imports = list(set(imports))

        # Classify imports
        resolved_imports: list[dict] = []
        local_imports: list[str] = []
        library_imports: list[str] = []

        for imp in imports:
            # Check if known library
            lib = self._classify_import(imp)
            if lib:
                library_imports.append(imp)
                resolved_imports.append({
                    "path": imp,
                    "type": "library",
                    "library": lib,
                    "chain": None,
                    "address": None,
                })
            else:
                local_imports.append(imp)
                # Try to find in cache (same chain, other contracts)
                resolved_addr = self._find_in_cache(chain, imp)
                if resolved_addr:
                    resolved_imports.append({
                        "path": imp,
                        "type": "contract",
                        "chain": chain,
                        "address": resolved_addr,
                    })
                    # Recursively resolve
                    await self._resolve_recursive(
                        chain, resolved_addr, graph, depth + 1, max_depth,
                    )
                else:
                    resolved_imports.append({
                        "path": imp,
                        "type": "unknown",
                        "chain": None,
                        "address": None,
                    })

        graph["nodes"][node_key] = {
            "chain": chain,
            "address": address,
            "depth": depth,
            "compiler_version": source.compiler_version,
            "file_count": len(source.sources),
            "imports": resolved_imports,
            "local_imports": local_imports,
            "library_imports": library_imports,
            "status": "resolved",
        }

        # Add edges
        for ri in resolved_imports:
            if ri["type"] == "contract" and ri["address"]:
                target_key = f"{ri['chain']}:{ri['address']}"
                graph["edges"].append({
                    "from": node_key,
                    "to": target_key,
                    "path": ri["path"],
                })

    def _classify_import(self, import_path: str) -> str | None:
        """Classify import as known library or None."""
        for prefix, name in KNOWN_LIBRARIES.items():
            if import_path.startswith(prefix):
                return name
        return None

    def _find_in_cache(self, chain: str, import_path: str) -> str | None:
        """Try to find a contract in cache by import path."""
        # This is a simplified heuristic — in production,
        # this would query verified contract mappings
        return None
