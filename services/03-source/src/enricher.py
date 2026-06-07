"""MetadataEnricher — Enrich source metadata dengan berbagai analisis.

Menambahkan intelligence ke source code:
  - Lines of code, function count
  - Security features (assembly, delegatecall, unchecked)
  - ERC standard detection
  - Framework detection
  - Complexity metrics
  - Proxy/upgradeability detection
"""

from __future__ import annotations

import re

import structlog

from src.models import EnrichedContract
from src.storage import EnhancedJSONStorage

log = structlog.get_logger()

# Patterns untuk deteksi fitur
_IMPORT_PATTERN = re.compile(r"import\s+(?:{[^}]*}\s+from\s+)?['\"]([^'\"]+)['\"]")
_FUNC_PATTERN = re.compile(r"function\s+\w+\s*\(")
_ASSEMBLY_PATTERN = re.compile(r"assembly\s*{")
_DELEGATECALL_PATTERN = re.compile(r"delegatecall")
_UNCHECKED_PATTERN = re.compile(r"unchecked\s*{")
_EXTERNAL_CALL_PATTERN = re.compile(r"\.call{")
_ERC_PATTERNS: dict[str, str] = {
    "ERC20": r"interface\s+IERC20|import.*IERC20|_transfer\s*\(|_mint\s*\(",
    "ERC721": r"interface\s+IERC721|import.*IERC721|_safeMint|_mint\s*\(.*msg\.sender",
    "ERC1155": r"interface\s+IERC1155|import.*IERC1155|_mintBatch",
    "ERC4626": r"interface\s+IERC4626|import.*IERC4626|asset\s*\(\s*\)\s*(?:public|external)",
    "ERC1967": r"ERC1967Proxy|UUPSUpgradeable|ProxyAdmin",
    "ERC2535": r"diamond|DiamondStorage|IDiamondCut",
}

_FRAMEWORK_PATTERNS: dict[str, str] = {
    "OpenZeppelin": r"@openzeppelin|openzeppelin",
    "Solmate": r"solmate",
    "Foundry": r"forge-std|forge-std",
    "Hardhat": r"hardhat",
    "Uniswap V2": r"@uniswap/v2-core|@uniswap/v2-periphery",
    "Uniswap V3": r"@uniswap/v3-core|@uniswap/v3-periphery",
    "Aave V3": r"@aave",
    "Chainlink": r"@chainlink",
}

_PROXY_PATTERNS: dict[str, str] = {
    "UUPS": r"UUPSUpgradeable|_authorizeUpgrade",
    "Transparent": r"TransparentUpgradeableProxy|ProxyAdmin",
    "Beacon": r"BeaconProxy|UpgradeableBeacon",
    "EIP-1967": r"ERC1967Proxy|ERC1967Upgrade",
    "0xSplits": r"Splits|Waterfall",
}


class MetadataEnricher:
    """Enrich source metadata dengan berbagai analisis.

    Usage::

        enricher = MetadataEnricher(storage)
        enriched = await enricher.enrich("ethereum", "0x...")
    """

    def __init__(self, storage: EnhancedJSONStorage) -> None:
        self.storage = storage

    async def enrich(self, chain: str, address: str) -> EnrichedContract | None:
        """Enrich contract metadata dengan berbagai analisis.

        Args:
            chain: Blockchain name.
            address: Contract address.

        Returns:
            EnrichedContract dengan metadata lengkap.
        """
        source = self.storage.get_source(chain, address)
        if not source:
            return None

        all_content = "\n".join(source.sources.values())

        # 1. Lines of code
        loc = sum(len(c.splitlines()) for c in source.sources.values())

        # 2. Function count
        functions = _FUNC_PATTERN.findall(all_content)

        # 3. Security features
        has_assembly = bool(_ASSEMBLY_PATTERN.search(all_content))
        has_delegatecall = bool(_DELEGATECALL_PATTERN.search(all_content))
        has_unchecked = bool(_UNCHECKED_PATTERN.search(all_content))
        has_external_call = bool(_EXTERNAL_CALL_PATTERN.search(all_content))
        has_oz = bool(re.search(r"@openzeppelin|openzeppelin", all_content, re.IGNORECASE))

        # 4. ERC standards
        erc_detected: list[str] = []
        for erc_name, pattern in _ERC_PATTERNS.items():
            if re.search(pattern, all_content, re.IGNORECASE):
                erc_detected.append(erc_name)

        # 5. Framework detection
        framework: str | None = None
        for fw_name, pattern in _FRAMEWORK_PATTERNS.items():
            if re.search(pattern, all_content, re.IGNORECASE):
                framework = fw_name
                break

        # 6. Complexity metrics
        nesting = self._max_nesting_depth(all_content)
        cyclomatic = self._calculate_cyclomatic(functions, all_content)

        # 7. Dependency count
        imports = _IMPORT_PATTERN.findall(all_content)
        dependencies = list(set(imports))

        # 8. Proxy detection
        is_proxy = False
        proxy_type: str | None = None
        for ptype, pattern in _PROXY_PATTERNS.items():
            if re.search(pattern, all_content, re.IGNORECASE):
                is_proxy = True
                proxy_type = ptype
                break

        # Get metadata from storage
        metadata = self.storage.get_metadata(chain, address)

        return EnrichedContract(
            chain=chain,
            address=address,
            name=metadata.source_hash[:8] if metadata else None,
            compiler_version=source.compiler_version,
            license=source.license,
            lines_of_code=loc,
            function_count=len(functions),
            file_count=len(source.sources),
            has_openzeppelin=has_oz,
            has_assembly=has_assembly,
            has_delegatecall=has_delegatecall,
            has_unchecked=has_unchecked,
            has_external_call=has_external_call,
            erc_detected=erc_detected,
            framework=framework,
            cyclomatic_complexity=round(cyclomatic, 2),
            nesting_depth=nesting,
            dependency_count=len(dependencies),
            dependencies=dependencies[:20],
            is_proxy=is_proxy,
            proxy_type=proxy_type,
            upgrade_count=metadata.upgrade_count if metadata else 0,
        )

    def _max_nesting_depth(self, content: str) -> int:
        """Hitung maximum nesting depth dari curly braces."""
        max_depth = 0
        current = 0
        in_string = False
        in_comment = False

        i = 0
        while i < len(content):
            c = content[i]
            nc = content[i + 1] if i + 1 < len(content) else ""

            # Skip strings
            if c in ('"', "'") and not in_comment:
                in_string = not in_string
            # Skip comments
            if c == "/" and nc == "/" and not in_string:
                in_comment = True
            if c == "\n":
                in_comment = False

            if not in_string and not in_comment:
                if c == "{":
                    current += 1
                    max_depth = max(max_depth, current)
                elif c == "}":
                    current = max(0, current - 1)

            i += 1

        return max_depth

    def _calculate_cyclomatic(self, functions: list, content: str) -> float:
        """Hitung cyclomatic complexity score."""
        if not functions:
            return 0.0

        decision_points = len(re.findall(
            r"\bif\s*\(|\belse\s+if\b|\bfor\s*\(|\bwhile\s*\(|\bcase\s+\w+|\bcatch\s*\(",
            content,
        ))

        len(re.findall(r"\breturn\s", content))

        # M = E - N + 2P (simplified)
        # For single function: cyclomatic = decision_points + 1
        complexity = (decision_points / max(len(functions), 1)) + 1

        return min(complexity, 50.0)  # Cap at 50
