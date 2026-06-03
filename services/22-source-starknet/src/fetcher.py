"""StarkNet source fetcher — multi-provider Cairo source code retrieval."""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from src.models import FetchResult

log = structlog.get_logger()

VOYAGER_API = "https://api.voyager.online/beta/contracts/{address}/code"
STARKSCAN_API = "https://api.starkscan.co/api/v0/contract/{address}/code"
GITHUB_SEARCH = "https://api.github.com/search/code?q={address}+language:cairo"


class StarkNetSourceFetcher:
    """Fetches Cairo smart contract source code from StarkNet explorers.

    Tries multiple sources in order: Voyager -> Starkscan -> GitHub.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"User-Agent": "Vyper-StarkNet-Fetcher/0.1.0"},
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch(self, address: str, contract_name: str = "") -> FetchResult:
        errors: list[str] = []
        result = FetchResult(address=address)

        source_files, compiler_version, abi, err = await self._try_voyager(address)
        if source_files:
            result.success = True
            result.source_files = source_files
            result.compiler_version = compiler_version or ""
            result.abi = abi
            result.contract_name = contract_name or self._extract_contract_name(source_files)
            return result
        if err:
            errors.append(f"voyager: {err}")

        source_files, compiler_version, abi, err = await self._try_starkscan(address)
        if source_files:
            result.success = True
            result.source_files = source_files
            result.compiler_version = compiler_version or ""
            result.abi = abi
            result.contract_name = contract_name or self._extract_contract_name(source_files)
            return result
        if err:
            errors.append(f"starkscan: {err}")

        source_files, compiler_version, abi, err = await self._try_github(address)
        if source_files:
            result.success = True
            result.source_files = source_files
            result.compiler_version = compiler_version or ""
            result.abi = abi
            result.contract_name = contract_name or self._extract_contract_name(source_files)
            return result
        if err:
            errors.append(f"github: {err}")

        result.errors = errors
        return result

    async def _try_voyager(self, address: str) -> tuple[dict[str, str] | None, str | None, list | None, str | None]:
        try:
            url = VOYAGER_API.format(address=address)
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return None, None, None, f"HTTP {resp.status_code}"
            data = resp.json()
            return self._parse_voyager_response(data)
        except Exception as exc:
            return None, None, None, str(exc)

    async def _try_starkscan(self, address: str) -> tuple[dict[str, str] | None, str | None, list | None, str | None]:
        try:
            url = STARKSCAN_API.format(address=address)
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return None, None, None, f"HTTP {resp.status_code}"
            data = resp.json()
            return self._parse_starkscan_response(data)
        except Exception as exc:
            return None, None, None, str(exc)

    async def _try_github(self, address: str) -> tuple[dict[str, str] | None, str | None, list | None, str | None]:
        try:
            url = GITHUB_SEARCH.format(address=address)
            resp = await self.client.get(url, headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code == 403:
                return None, None, None, "GitHub rate limit exceeded"
            if resp.status_code != 200:
                return None, None, None, f"HTTP {resp.status_code}"
            data = resp.json()
            if data.get("total_count", 0) == 0:
                return None, None, None, "No matching Cairo files found on GitHub"
            return None, None, None, "GitHub raw fetch not implemented"
        except Exception as exc:
            return None, None, None, str(exc)

    def _parse_voyager_response(self, data: dict) -> tuple[dict[str, str] | None, str | None, list | None, str | None]:
        source_files: dict[str, str] = {}
        compiler_version: str | None = None
        abi: list | None = None

        if isinstance(data, list):
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name", entry.get("filename", f"source_{len(source_files)}.cairo"))
                code = entry.get("source", entry.get("code", entry.get("content", "")))
                if code:
                    source_files[name] = code
                if not compiler_version:
                    compiler_version = entry.get("compiler_version", entry.get("compilerVersion"))
                if not abi:
                    abi = entry.get("abi")
        elif isinstance(data, dict):
            source_files = self._extract_source_files(data)
            compiler_version = data.get("compiler_version", data.get("compilerVersion"))
            abi = data.get("abi")

        if not source_files:
            return None, None, None, "No source code in Voyager response"

        return source_files, compiler_version, abi, None

    def _parse_starkscan_response(self, data: dict) -> tuple[dict[str, str] | None, str | None, list | None, str | None]:
        source_files = self._extract_source_files(data)
        if not source_files:
            return None, None, None, "No source code in Starkscan response"

        compiler_version = data.get("compiler_version", data.get("compilerVersion"))
        abi = data.get("abi")
        return source_files, compiler_version, abi, None

    def _extract_source_files(self, data: dict) -> dict[str, str]:
        source_files: dict[str, str] = {}

        for key in ("source_files", "files", "sources"):
            val = data.get(key)
            if isinstance(val, dict):
                for name, content in val.items():
                    if isinstance(content, str) and content.strip():
                        source_files[name] = content
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        name = item.get("name", item.get("filename", f"source_{len(source_files)}.cairo"))
                        content = item.get("source", item.get("code", item.get("content", "")))
                        if content:
                            source_files[name] = content

        if not source_files:
            source = data.get("source", data.get("code", data.get("content", "")))
            if isinstance(source, str) and source.strip():
                name = data.get("name", data.get("filename", "contract.cairo"))
                source_files[name] = source

        if not source_files:
            contract_name = data.get("contract_name", data.get("name", "contract"))
            source = data.get("source_code", data.get("sourceCode", data.get("sourcecode", "")))
            if isinstance(source, str) and source.strip():
                source_files[f"{contract_name}.cairo"] = source

        return source_files

    @staticmethod
    def _extract_contract_name(source_files: dict[str, str]) -> str:
        for name in source_files:
            if name.endswith(".cairo"):
                match = re.search(r"#\s*@contract\s+(\w+)", source_files[name])
                if match:
                    return match.group(1)
                match = re.search(r"^module\s+(\w+)", source_files[name], re.MULTILINE)
                if match:
                    return match.group(1)
        return "UnknownContract"
