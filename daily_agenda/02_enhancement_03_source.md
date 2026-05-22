# Enhancement Plan: Service 03 — Source Code Intelligence

> **Service saat ini**: Fetch verified Solidity source code dari 4 provider (Etherscan, Sourcify, Blockscout, GitHub), cache ke disk.
> **Port**: 8002  |  **Version**: 0.1.0

---

## Daftar Isi

1. [Arsitektur Saat Ini](#1-arsitektur-saat-ini)
2. [Critical Gaps](#2-critical-gaps)
3. [Enhancement Level 1 — Foundation (Minggu 1)](#3-enhancement-level-1--foundation-minggu-1)
4. [Enhancement Level 2 — Intelligence (Minggu 2)](#4-enhancement-level-2--intelligence-minggu-2)
5. [Enhancement Level 3 — Autonomous (Minggu 3)](#5-enhancement-level-3--autonomous-minggu-3)
6. [Enhancement Level 4 — God-Tier (Minggu 4+)](#6-enhancement-level-4--god-tier-minggu-4)
7. [Roadmap](#7-roadmap)

---

## 1. Arsitektur Saat Ini

```
┌───────────────────────────────────────────────────────────┐
│                      03-source                             │
│                                                           │
│  POST /fetch ──► SourceDetector.fetch()                   │
│                      │                                    │
│                      ▼                                    │
│  ┌─────────────────────────────────────┐                  │
│  │  Provider Registry (ordered)        │                  │
│  │                                     │                  │
│  │  1. EtherscanProvider   (API key)   │                  │
│  │  2. SourcifyProvider    (public)    │                  │
│  │  3. BlockscoutProvider  (public)    │                  │
│  │  4. GitHubProvider      (public)    │                  │
│  └─────────────────────────────────────┘                  │
│                      │                                    │
│                      ▼                                    │
│  ┌─────────────────────────────────────┐                  │
│  │  Disk Cache                          │                  │
│  │  /data/source/contracts/{chain}/     │                  │
│  │       {address}/                     │                  │
│  │           metadata.json              │                  │
│  │           sources/*.sol              │                  │
│  └─────────────────────────────────────┘                  │
│                                                           │
│  Endpoints:                                               │
│    POST /fetch                    (fetch + cache)         │
│    GET  /source/{chain}/{address} (from cache)            │
│    DELETE /source/{chain}/{address} (clear cache)         │
│    GET  /providers                (list providers)        │
└───────────────────────────────────────────────────────────┘
```

### Kelemahan Fundamental Saat Ini:

1. **Hanya fetch — tidak ada analisis**: Source diambil, disimpan, tapi tidak diproses lebih lanjut
2. **Cache flat file**: Rawan corruption, tidak ada indexing, tidak ada search
3. **4 provider saja**: Banyak chain tidak tercover (zkSync, StarkNet, Arbitrum Nova, dll)
4. **No compiler validation**: Tidak verifikasi bahwa source == on-chain bytecode
5. **No diff tracking**: Tidak track perubahan source code (kontrak upgrade)
6. **No metadata enrichment**: Tidak tambahin data seperti ABI, AST, bytecode
7. **Tidak ada verifikasi metadata**: `license`, `constructor_args` tidak selalu akurat
8. **Single contract per request**: Tidak bisa batch fetch

---

## 2. Critical Gaps

| Gap | Dampak | Priority |
|-----|--------|----------|
| No compiler verification | Source bisa dimanipulasi | 🔴 Critical |
| Coverage terbatas (4 provider) | Banyak chain tidak tercover | 🔴 Critical |
| No bytecode comparison | Tidak tahu kontrak upgrade | 🔴 Critical |
| No ABI extraction | Scanner butuh ABI untuk analisis | 🟡 High |
| No incremental fetch | Fetch ulang dari awal terus | 🟡 High |
| No batch endpoint | Slow untuk banyak kontrak | 🟡 High |
| No search/index | Tidak bisa cari kontrak by name | 🟢 Medium |

---

## 3. Enhancement Level 1 — Foundation (Minggu 1)

### 3.1 Provider Expansion: 10+ Provider Baru

```python
# src/providers/__init__.py
PROVIDER_REGISTRY = {
    # Existing
    "etherscan":    EtherscanProvider(),
    "sourcify":     SourcifyProvider(),
    "blockscout":   BlockscoutProvider(),
    "github":       GitHubProvider(),
    
    # New — EVM chains
    "etherscan_arbitrum":  EtherscanChainProvider("arbitrum"),
    "etherscan_optimism":  EtherscanChainProvider("optimism"),
    "etherscan_polygon":   EtherscanChainProvider("polygon"),
    "etherscan_bsc":       EtherscanChainProvider("bsc"),
    "etherscan_avalanche": EtherscanChainProvider("avalanche"),
    "etherscan_base":      EtherscanChainProvider("base"),
    
    # New — Specialized
    "etherscan_zk_sync":   ZkSyncProvider(),       # zkSync Era
    "etherscan_starknet":  StarkNetProvider(),      # StarkNet (Cairo)
    "etherscan_scroll":    ScrollProvider(),
    "etherscan_linea":     LineaProvider(),
    "etherscan_celo":      CeloProvider(),
    
    # New — Alternative explorers
    "routescan":  RoutescanProvider(),   # Multi-chain (arbitrum, optimism, etc.)
    "novascan":   NovaScanProvider(),    # Arbitrum Nova
    
    # New — Direct node RPC
    "eth_call":   EthCallProvider(),     # Via eth_call + eth_getCode
    "ipfs":       IPFSProvider(),        # Source tersimpan di IPFS
}
```

**EtherscanChainProvider** — generalisasi untuk semua chain Etherscan-like:
```python
class EtherscanChainProvider:
    """Generic Etherscan-like provider untuk berbagai chain."""
    
    CHAIN_CONFIGS = {
        "arbitrum": {
            "url": "https://api.arbiscan.io/api",
            "api_key_env": "ARBISCAN_API_KEY",
        },
        "optimism": {
            "url": "https://api-optimistic.etherscan.io/api",
            "api_key_env": "OPTIMISM_API_KEY",
        },
        "polygon": {
            "url": "https://api.polygonscan.com/api",
            "api_key_env": "POLYGONSCAN_API_KEY",
        },
        "bsc": {
            "url": "https://api.bscscan.com/api",
            "api_key_env": "BSCSCAN_API_KEY",
        },
        "avalanche": {
            "url": "https://api.snowtrace.io/api",
            "api_key_env": "SNOWTRACE_API_KEY",
        },
        "base": {
            "url": "https://api.basescan.org/api",
            "api_key_env": "BASESCAN_API_KEY",
        },
    }
    
    def __init__(self, chain: str):
        self.chain = chain
        config = self.CHAIN_CONFIGS[chain]
        self.base_url = config["url"]
        self.api_key = os.getenv(config["api_key_env"])
    
    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        """Fetch via chain-specific Etherscan API."""
        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": self.api_key or "",
        }
        resp = await self.client.get(self.base_url, params=params)
        data = resp.json()
        
        if data["status"] != "1":
            return None
        
        result = data["result"][0]
        if result["SourceCode"] == "":
            return None
        
        return SourceResult(
            sources=self._parse_source_code(result["SourceCode"]),
            compiler_version=result["CompilerVersion"],
            license=result.get("LicenseType"),
            provider=f"etherscan_{self.chain}",
            constructor_args=result.get("ConstructorArguments"),
        )
```

### 3.2 Database Upgrade: SQLite → PostgreSQL

```sql
-- Main contracts table
CREATE TABLE contracts (
    id                  SERIAL PRIMARY KEY,
    chain               TEXT NOT NULL,
    address             TEXT NOT NULL,
    checksum_address    TEXT,
    name                TEXT,
    
    -- Source metadata
    compiler_version    TEXT,
    license             TEXT,
    provider            TEXT,
    constructor_args    TEXT,
    
    -- Enriched metadata
    abi                 JSONB,
    bytecode            TEXT,
    bytecode_hash       TEXT,      -- Keccak256(bytecode) untuk verifikasi
    source_hash         TEXT,      -- Keccak256(source) untuk tracking changes
    
    -- Stats
    lines_of_code       INT DEFAULT 0,
    file_count          INT DEFAULT 0,
    
    -- Audit trail
    first_fetched_at    TIMESTAMPTZ DEFAULT NOW(),
    last_fetched_at     TIMESTAMPTZ DEFAULT NOW(),
    fetch_count         INT DEFAULT 1,
    
    UNIQUE(chain, address)
);

-- Source files (one per contract file)
CREATE TABLE source_files (
    id                  SERIAL PRIMARY KEY,
    contract_id         INT REFERENCES contracts(id) ON DELETE CASCADE,
    filename            TEXT NOT NULL,
    content             TEXT NOT NULL,
    content_hash        TEXT,      -- Untuk deduplikasi
    line_count          INT DEFAULT 0,
    UNIQUE(contract_id, filename)
);

-- Historical versions (track upgrades)
CREATE TABLE contract_versions (
    id                  SERIAL PRIMARY KEY,
    contract_id         INT REFERENCES contracts(id) ON DELETE CASCADE,
    source_version      INT NOT NULL,  -- Increment per change
    bytecode_hash       TEXT,
    source_hash         TEXT,
    block_number        BIGINT,        -- Block where this version was deployed
    tx_hash             TEXT,          -- Deployment transaction
    detected_at         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(contract_id, source_version)
);

-- Dependencies (import graph)
CREATE TABLE contract_dependencies (
    id                  SERIAL PRIMARY KEY,
    contract_id         INT REFERENCES contracts(id) ON DELETE CASCADE,
    dependency_address  TEXT NOT NULL,
    dependency_chain    TEXT NOT NULL,
    import_path         TEXT,
    is_direct           BOOLEAN DEFAULT TRUE,
    UNIQUE(contract_id, dependency_chain, dependency_address)
);

-- Full-text search index
CREATE INDEX idx_contracts_search ON contracts USING GIN(
    to_tsvector('english', name || ' ' || COALESCE(abi::text, ''))
);

-- Cache invalidation tracking
CREATE TABLE fetch_queue (
    id                  SERIAL PRIMARY KEY,
    chain               TEXT NOT NULL,
    address             TEXT NOT NULL,
    priority            INT DEFAULT 5,   -- 1 (highest) to 10 (lowest)
    status              TEXT DEFAULT 'pending',  -- pending/running/completed/failed
    scheduled_at        TIMESTAMPTZ DEFAULT NOW(),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    error               TEXT,
    UNIQUE(chain, address)
);
```

### 3.3 Compiler Verification Engine

Verifikasi bahwa source code yang di-fetch cocok dengan bytecode di on-chain:

```python
class CompilerVerifier:
    """Verifikasi source code match dengan on-chain bytecode."""
    
    async def verify(self, chain: str, address: str) -> VerificationResult:
        """Verifikasi source == bytecode dengan re-compile."""
        
        # 1. Fetch source
        source = await self.detector.get_cached(chain, address)
        if not source:
            return VerificationResult(verified=False, reason="No source cached")
        
        # 2. Fetch on-chain bytecode
        bytecode = await self._fetch_bytecode(chain, address)
        if not bytecode:
            return VerificationResult(verified=False, reason="Cannot fetch bytecode")
        
        # 3. Strip metadata hash dari bytecode
        # Solidity append IPFS/Swarm hash di akhir bytecode
        cleaned_bytecode = self._strip_metadata(bytecode)
        
        # 4. Compile source dengan versi yang sama
        compiled = await self._compile_source(source)
        if not compiled:
            return VerificationResult(verified=False, reason="Compilation failed")
        
        # 5. Compare bytecode (tanpa metadata hash)
        is_match = self._compare_bytecode(
            compiled.bytecode,
            cleaned_bytecode,
            ignore_metadata=True,
        )
        
        if is_match:
            # Hitung persentase match
            match_pct = self._calculate_match_percentage(
                compiled.bytecode,
                cleaned_bytecode,
            )
            return VerificationResult(
                verified=True,
                match_percentage=match_pct,
                compiler_version=source.compiler_version,
                metadata_hash=compiled.metadata_hash,
            )
        else:
            # Coba dengan optimizer settings berbeda
            for settings in self._try_optimizer_settings(source):
                compiled = await self._compile_with_settings(source, settings)
                if self._compare_bytecode(compiled.bytecode, cleaned_bytecode):
                    return VerificationResult(
                        verified=True,
                        optimized=True,
                        optimizer_settings=settings,
                    )
            
            return VerificationResult(
                verified=False,
                reason="Bytecode mismatch — source may differ from deployed contract",
                expected_hash=keccak(cleaned_bytecode),
                actual_hash=keccak(compiled.bytecode),
            )
    
    def _strip_metadata(self, bytecode: str) -> str:
        """Strip the IPFS/Swarm metadata hash from the end of bytecode.
        
        Solidity appends: a265... (CBOR-encoded metadata)
        The last 2 bytes indicate the length of the metadata.
        """
        if len(bytecode) < 40:
            return bytecode
        
        # Read the last 2 bytes as metadata length
        meta_length = int(bytecode[-4:], 16) * 2 + 4  # In hex chars
        if meta_length < len(bytecode):
            return bytecode[:-meta_length]
        return bytecode
```

### 3.4 New Endpoints Level 1

```python
@router.post("/fetch/batch")
async def fetch_batch(body: BatchFetchRequest):
    """Batch fetch multiple contracts sekaligus."""
    tasks = [detector.fetch(item.chain, item.address) for item in body.contracts]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return ok([
        {"chain": c.chain, "address": c.address, "result": r}
        for c, r in zip(body.contracts, results)
    ])

@router.get("/verify/{chain}/{address}")
async def verify_contract(chain: str, address: str):
    """Verify source == on-chain bytecode."""
    verifier = CompilerVerifier()
    result = await verifier.verify(chain, address)
    return ok(result)

@router.get("/contracts/search")
async def search_contracts(
    query: str,
    chain: str = None,
    limit: int = 20,
):
    """Search contracts by name, address, or ABI."""
    pass

@router.get("/contracts/{chain}/{address}/metadata")
async def get_contract_metadata(chain: str, address: str):
    """Dapatkan metadata lengkap: ABI, bytecode, dependencies."""
    pass

@router.get("/cache/stats")
async def get_cache_stats():
    """Statistik cache: total contracts, per chain, dll."""
    pass
```

---

## 4. Enhancement Level 2 — Intelligence (Minggu 2)

### 4.1 ABI Extraction & AST Parsing

```python
class AbiExtractor:
    """Extract ABI dari source code tanpa compile ulang."""
    
    async def extract(self, source: SourceResult) -> ContractABI:
        """Extract ABI menggunakan multiple methods."""
        
        # Method 1: Dari metadata (jika ada)
        if source.abi:
            return self._parse_abi(source.abi)
        
        # Method 2: Via Etherscan API (ABI sudah tersedia)
        abi = await self._fetch_abi_from_explorer(source)
        if abi:
            return abi
        
        # Method 3: Parse manual dari source (regex-based)
        return await self._parse_from_source(source)
    
    async def _parse_from_source(self, source) -> ContractABI:
        """Parse ABI dari Solidity source menggunakan regex + pattern matching."""
        functions = []
        events = []
        errors = []
        
        for filename, content in source.sources.items():
            # Parse function signatures
            func_pattern = re.compile(
                r"function\s+(\w+)\s*\(([^)]*)\)\s*"
                r"(?:public|external|internal|private)?"
                r"(?:\s*(?:pure|view|payable))?"
            )
            for match in func_pattern.finditer(content):
                name = match.group(1)
                params = self._parse_params(match.group(2))
                
                sig = f"{name}({','.join(p['type'] for p in params)})"
                selector = keccak(sig.encode())[:4].hex()
                
                functions.append(FunctionABI(
                    name=name,
                    signature=sig,
                    selector=f"0x{selector}",
                    inputs=params,
                    state_mutability=self._detect_mutability(match.group(0)),
                ))
        
        return ContractABI(
            functions=functions,
            events=events,
            errors=errors,
            raw_abi=self._to_json_abi(functions, events, errors),
        )
```

### 4.2 Dependency Graph & Import Resolution

```python
class DependencyResolver:
    """Resolve all dependencies (imports) untuk satu kontrak."""
    
    async def resolve(
        self,
        chain: str,
        address: str,
        max_depth: int = 3,
    ) -> DependencyGraph:
        """Resolve semua dependency secara rekursif."""
        
        graph = DependencyGraph(root=address)
        await self._resolve_recursive(chain, address, graph, depth=0, max_depth=max_depth)
        return graph
    
    async def _resolve_recursive(
        self, chain, address, graph, depth, max_depth,
    ):
        if depth >= max_depth:
            return
        
        source = await self.detector.get_cached(chain, address)
        if not source:
            return
        
        # Parse import statements
        for filename, content in source.sources.items():
            imports = re.findall(
                r"import\s+(?:{[^}]*}\s+from\s+)?['\"]([^'\"]+)['\"]",
                content,
            )
            
            for import_path in imports:
                # Resolve import ke contract address
                resolved = await self._resolve_import(
                    chain=chain,
                    import_path=import_path,
                    context=address,
                )
                
                if resolved:
                    graph.add_edge(address, resolved.address, import_path)
                    
                    # Recurse
                    await self._resolve_recursive(
                        chain, resolved.address,
                        graph, depth + 1, max_depth,
                    )
    
    async def _resolve_import(self, chain, import_path, context) -> ResolvedImport | None:
        """Resolve import path ke contract address."""
        
        # 1. Check local cache
        cached = await self.db.query("""
            SELECT * FROM contract_dependencies 
            WHERE import_path = $1 AND chain = $2
        """, import_path, chain)
        if cached:
            return cached
        
        # 2. Try known mappings (OpenZeppelin, etc.)
        if "openzeppelin" in import_path.lower():
            return await self._resolve_oz_import(import_path)
        
        # 3. Try to find via Sourcify full match
        sourcify = SourcifyProvider()
        result = await sourcify.fetch_by_metadata(chain, import_path)
        if result:
            return result
        
        return None
```

### 4.3 Source Diff Tracking (Upgrade Detection)

```python
class UpgradeDetector:
    """Deteksi ketika smart contract di-upgrade (implementation change)."""
    
    async def check_upgrade(
        self,
        chain: str,
        address: str,
        proxy_address: str = None,
    ) -> UpgradeInfo | None:
        """Cek apakah kontrak pernah di-upgrade."""
        
        # 1. Get current bytecode
        current_bytecode = await self._fetch_bytecode(chain, address)
        current_hash = keccak(current_bytecode.encode()).hex()
        
        # 2. Check historical versions di database
        versions = await self.db.query("""
            SELECT * FROM contract_versions
            WHERE contract_id = (
                SELECT id FROM contracts 
                WHERE chain = $1 AND address = $2
            )
            ORDER BY source_version DESC
        """, chain, address)
        
        if not versions:
            # First time — record current version
            await self._record_version(chain, address, current_hash, None)
            return None
        
        latest = versions[0]
        
        # 3. Compare bytecode hash
        if current_hash != latest.bytecode_hash:
            # Contract has been upgraded!
            changes = await self._analyze_changes(
                chain, address,
                latest.bytecode_hash,
                current_hash,
            )
            
            # Record new version
            await self._record_version(
                chain, address, current_hash,
                latest.source_version + 1,
            )
            
            return UpgradeInfo(
                upgraded=True,
                previous_version=latest.source_version,
                current_version=latest.source_version + 1,
                changes=changes,
                detected_at=datetime.now(),
                # Alert
                severity="high" if changes.critical else "medium",
                description=self._describe_upgrade(changes),
            )
        
        return None  # No upgrade
    
    async def _analyze_changes(
        self, chain, address, old_hash, new_hash,
    ) -> CodeChanges:
        """Analisis perbedaan antara dua versi bytecode."""
        
        # Fetch old and new source
        old_source = await self._get_source_by_hash(chain, address, old_hash)
        new_source = await self._get_source_by_hash(chain, address, new_hash)
        
        if not old_source or not new_source:
            return CodeChanges(unknown=True)
        
        # Git-style diff
        import difflib
        
        changes = CodeChanges()
        
        for filename in set(list(old_source.keys()) + list(new_source.keys())):
            old_content = old_source.get(filename, "")
            new_content = new_source.get(filename, "")
            
            diff = list(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{filename}",
                tofile=f"b/{filename}",
            ))
            
            if diff:
                changes.files_changed.append(filename)
                changes.diff[filename] = diff
                
                # Analisis perubahan berbahaya
                changes.critical = self._check_critical_changes(diff) or changes.critical
                changes.added_functions += self._count_added_functions(diff)
                changes.removed_functions += self._count_removed_functions(diff)
                changes.modified_functions += self._count_modified_functions(diff)
                
                # Deteksi backdoor
                if self._detect_backdoor(diff):
                    changes.backdoor_detected = True
                    changes.severity = "CRITICAL"
        
        return changes
```

### 4.4 Source Metadata Enrichment Pipeline

```python
class MetadataEnricher:
    """Enrich source metadata dengan berbagai analisis."""
    
    async def enrich(self, chain: str, address: str) -> EnrichedContract:
        source = await self.detector.get_cached(chain, address)
        if not source:
            return None
        
        enriched = EnrichedContract(
            chain=chain,
            address=address,
            source=source,
        )
        
        # 1. Lines of code
        enriched.lines_of_code = sum(
            len(c.splitlines()) for c in source.sources.values()
        )
        
        # 2. Function count
        enriched.function_count = self._count_functions(source)
        
        # 3. Security features
        enriched.has_openzeppelin = self._check_oz_usage(source)
        enriched.has_assembly = "assembly " in str(source.sources)
        enriched.has_delegatecall = "delegatecall" in str(source.sources)
        enriched.has_unchecked = "unchecked {" in str(source.sources)
        
        # 4. Standards compliance
        enriched.erc_detected = self._detect_erc_standards(source)
        # ERC-20, ERC-721, ERC-1155, ERC-4626, dll
        
        # 5. Framework detection
        enriched.framework = self._detect_framework(source)
        # OpenZeppelin, Solmate, Foundry, Hardhat, dll
        
        # 6. Complexity metrics
        enriched.cyclomatic_complexity = self._calculate_cyclomatic(source)
        enriched.nesting_depth = self._max_nesting_depth(source)
        
        # 7. Dependency count
        enriched.dependency_count = self._count_imports(source)
        
        # 8. Upgradeability
        enriched.is_proxy = self._detect_proxy(source)
        enriched.proxy_type = self._classify_proxy(source)
        # UUPS, Transparent, Beacon, 0xSplits, dll
        
        return enriched
```

### 4.5 New Endpoints Level 2

```python
@router.get("/contracts/{chain}/{address}/abi")
async def get_contract_abi(chain: str, address: str):
    """Dapatkan ABI contract."""
    pass

@router.get("/contracts/{chain}/{address}/dependencies")
async def get_contract_dependencies(chain: str, address: str, max_depth: int = 3):
    """Dapatkan dependency graph."""
    pass

@router.get("/contracts/{chain}/{address}/upgrades")
async def get_contract_upgrades(chain: str, address: str):
    """History upgrade kontrak."""
    pass

@router.get("/contracts/{chain}/{address}/enriched")
async def get_enriched_metadata(chain: str, address: str):
    """Dapatkan metadata lengkap + enrichment."""
    pass

@router.get("/contracts/{chain}/{address}/security")
async def get_security_metadata(chain: str, address: str):
    """Dapatkan security-relevant metadata."""
    pass

@router.post("/contracts/{chain}/{address}/refresh")
async def refresh_contract(chain: str, address: str):
    """Force re-fetch + re-verify + re-enrich."""
    pass
```

---

## 5. Enhancement Level 3 — Autonomous (Minggu 3)

### 5.1 Real-Time Block Monitor

```python
class BlockMonitor:
    """Monitor blockchain untuk contract baru secara real-time."""
    
    # Chain configurations
    CHAINS = {
        "ethereum": {
            "rpc": "https://eth.drpc.org",
            "start_block": 19_500_000,  # Recent
        },
        "polygon": {
            "rpc": "https://polygon.drpc.org",
            "start_block": 50_000_000,
        },
        "arbitrum": {
            "rpc": "https://arbitrum.drpc.org",
            "start_block": 200_000_000,
        },
        # + 15 chains lainnya
    }
    
    async def start(self):
        """Start monitoring untuk semua chain."""
        for chain, config in self.CHAINS.items():
            asyncio.create_task(self._monitor_chain(chain, config))
    
    async def _monitor_chain(self, chain: str, config: dict):
        """Monitor satu chain untuk contract creations."""
        w3 = Web3(Web3.AsyncHTTPProvider(config["rpc"]))
        
        # Track block terakhir
        last_block = config["start_block"]
        
        while True:
            try:
                current_block = await w3.eth.block_number
                
                if current_block > last_block:
                    # Process new blocks
                    for block_num in range(last_block + 1, current_block + 1):
                        block = await w3.eth.get_block(block_num, full_transactions=True)
                        
                        for tx in block.transactions:
                            if tx.to is None:  # Contract creation
                                receipt = await w3.eth.get_transaction_receipt(tx.hash)
                                contract_address = receipt.contractAddress
                                
                                # Auto-fetch source jika terverifikasi
                                asyncio.create_task(
                                    self._try_fetch(chain, contract_address)
                                )
                    
                    last_block = current_block
                
                await asyncio.sleep(12)  # 12 detik (1 block Ethereum)
                
            except Exception as e:
                log.error(f"BlockMonitor.{chain}.error", error=str(e))
                await asyncio.sleep(60)
    
    async def _try_fetch(self, chain: str, address: str):
        """Coba fetch source untuk contract baru."""
        # Tunggu beberapa detik agar validator sempat verify
        await asyncio.sleep(30)
        
        result = await self.detector.fetch(chain, address)
        if result:
            # Trigger scan via orchestrator
            await self.orchestrator.submit({
                "chain": chain,
                "address": address,
                "source": result,
                "source_type": "new_contract",
            })
            
            # Alert via Service 10 (Notifier)
            await self.notifier.send(
                channel="discord",
                message=f"🆕 New verified contract: {chain}/{address}",
            )
```

### 5.2 Proactive Cache Warming

```python
class CacheWarmer:
    """Proaktif fetch source untuk kontrak-kontrak terkenal."""
    
    WARM_LISTS = {
        "defi_blue_chips": [
            # Uniswap
            {"chain": "ethereum", "address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"},
            {"chain": "ethereum", "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"},
            # Aave
            {"chain": "ethereum", "address": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"},
            # Compound
            {"chain": "ethereum", "address": "0xc00e94Cb662C3520282E6f5717214004A7f26888"},
            # MakerDAO
            {"chain": "ethereum", "address": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2"},
            # +500 kontrak lainnya
        ],
        "recently_hacked": [],  # Auto-populated from incident DB
        "high_tvl": [],         # Auto-populated from DeFiLlama
        "recently_audited": [], # Auto-populated from Service 02
    }
    
    async def warm(self):
        """Warm cache untuk semua kontrak di warm lists."""
        for category, contracts in self.WARM_LISTS.items():
            log.info("cache_warm.starting", category=category, count=len(contracts))
            
            batch_size = 10
            for i in range(0, len(contracts), batch_size):
                batch = contracts[i:i + batch_size]
                tasks = [
                    self.detector.fetch(c["chain"], c["address"])
                    for c in batch
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                log.info("cache_warm.progress", category=category, done=i + len(batch))
                await asyncio.sleep(1)  # Rate limiting
```

### 5.3 Integration with Service 08 (Exploit Engine)

```python
class ExploitSourceIntegration:
    """Integrasi dengan Exploit Engine untuk auto-generate PoC."""
    
    async def auto_exploit_pipeline(
        self,
        chain: str,
        address: str,
        finding_type: str = "auto",
    ) -> dict:
        """Full pipeline: fetch → analyze → exploit."""
        
        # 1. Fetch source
        source = await self.detector.fetch(chain, address)
        if not source:
            return {"error": "Source not available"}
        
        # 2. Kirim ke orchestrator untuk full scan
        scan_result = await self.orchestrator.submit_scan(
            source=source.sources,
            chain=chain,
            address=address,
        )
        
        # 3. Jika ada finding, generate PoC
        if scan_result.findings:
            exploit_results = []
            for finding in scan_result.findings[:3]:  # Top 3
                poc = await self.exploit_engine.run(
                    source=source.sources,
                    finding_id=finding.id,
                    attack_type=finding.attack_type,
                    vulnerable_function=finding.function,
                )
                exploit_results.append(poc)
            
            return {
                "contract": f"{chain}/{address}",
                "findings_count": len(scan_result.findings),
                "exploits_generated": len(exploit_results),
                "top_poc": exploit_results[0] if exploit_results else None,
            }
        
        return {"contract": f"{chain}/{address}", "findings": "none"}
```

### 5.4 New Endpoints Level 3

```python
@router.post("/monitor/start")
async def start_block_monitor(chains: list[str] = None):
    """Start real-time block monitoring."""
    pass

@router.post("/monitor/stop")
async def stop_block_monitor():
    """Stop block monitoring."""
    pass

@router.get("/monitor/status")
async def get_monitor_status():
    """Status block monitoring."""
    pass

@router.post("/cache/warm")
async def trigger_cache_warm():
    """Trigger cache warming."""
    pass

@router.get("/contracts/{chain}/{address}/auto-exploit")
async def auto_exploit_contract(chain: str, address: str):
    """Full pipeline: fetch → scan → exploit."""
    pass
```

---

## 6. Enhancement Level 4 — God-Tier (Minggu 4+)

### 6.1 Multi-Version Bytecode Repository

Buat repository bytecode untuk semua versi kontrak:

```python
class BytecodeRepository:
    """Repository bytecode untuk semua versi kontrak."""
    
    async def store_bytecode(self, chain, address, block_number):
        """Simpan bytecode di block tertentu."""
        bytecode = await self._fetch_bytecode(chain, address, block_number)
        
        await self.db.execute("""
            INSERT INTO bytecode_snapshots (chain, address, block_number, bytecode, bytecode_hash)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (chain, address, block_number) DO NOTHING
        """, chain, address, block_number, bytecode, keccak(bytecode.encode()).hex())
    
    async def diff_bytecode(self, chain, address, from_block, to_block):
        """Diff bytecode antara dua block."""
        old = await self._get_bytecode_at_block(chain, address, from_block)
        new = await self._get_bytecode_at_block(chain, address, to_block)
        
        if old == new:
            return {"changed": False}
        
        # Analisis opcode-level diff
        old_ops = self._disassemble(old)
        new_ops = self._disassemble(new)
        
        return {
            "changed": True,
            "from_block": from_block,
            "to_block": to_block,
            "changed_functions": self._detect_function_changes(old_ops, new_ops),
            "new_opcodes": [op for op in new_ops if op not in old_ops],
            "removed_opcodes": [op for op in old_ops if op not in new_ops],
        }
```

### 6.2 AI-Powered Source Reconstruction

Untuk kontrak yang **tidak terverifikasi**, rekonstruksi source dari bytecode:

```python
class AISourceReconstructor:
    """Rekonstruksi Solidity source dari bytecode menggunakan AI."""
    
    async def reconstruct(self, bytecode: str) -> ReconstructedSource:
        """Rekonstruksi source code dari bytecode."""
        
        # 1. Decompile ke psuedocode
        decompiled = await self._decompile(bytecode)
        
        # 2. Deteksi pattern yang dikenal
        patterns = self._detect_known_patterns(decompiled)
        # ERC-20, ERC-721, Uniswap V2/V3, OpenZeppelin, dll
        
        # 3. Generate source skeleton
        skeleton = self._generate_skeleton(patterns)
        
        # 4. AI generate nama fungsi & variable
        enriched = await self._ai_enrich_names(decompiled, skeleton)
        
        # 5. Estimate akurasi
        accuracy = self._estimate_accuracy(decompiled, patterns)
        
        return ReconstructedSource(
            source=enriched,
            confidence=accuracy,
            detected_patterns=patterns,
            is_verified_source_available=False,
            recommendation=(
                "Source tidak terverifikasi. Gunakan hasil rekonstruksi "
                "dengan hati-hati — akurasi tidak 100%."
            ),
        )
    
    async def _decompile(self, bytecode: str) -> dict:
        """Decompile bytecode menggunakan tool eksternal."""
        # Gunakan heimdall, pyevmasm, atau API dedaub
        pass
    
    async def _ai_enrich_names(self, decompiled, skeleton) -> str:
        """Gunakan LLM untuk memberi nama fungsi & variable."""
        prompt = f"""
        Given this decompiled smart contract bytecode:
        
        Functions:
        {decompiled['functions']}
        
        Storage layout:
        {decompiled['storage']}
        
        Events:
        {decompiled['events']}
        
        Generate meaningful names for all functions and state variables.
        This appears to be a {skeleton['contract_type']} contract.
        """
        
        resp = await self.ai_service.chat(prompt)
        return self._apply_names(skeleton, resp.names)
```

### 6.3 Cross-Chain Source Correlation

```python
class CrossChainCorrelator:
    """Korelasi source code di berbagai chain."""
    
    async def find_same_contract(self, bytecode_hash: str) -> list[CrossChainEntry]:
        """Cari kontrak dengan bytecode yang sama di chain lain."""
        
        return await self.db.query("""
            SELECT chain, address, name, first_fetched_at
            FROM contracts
            WHERE bytecode_hash = $1
            ORDER BY chain
        """, bytecode_hash)
    
    async def find_similar_contracts(
        self, chain: str, address: str, threshold: float = 0.9,
    ) -> list[SimilarContract]:
        """Cari kontrak dengan source serupa (fork detection)."""
        
        source = await self.detector.get_cached(chain, address)
        if not source:
            return []
        
        all_contracts = await self.db.query("SELECT * FROM contracts")
        
        similar = []
        for c in all_contracts:
            if c.chain == chain and c.address == address.lower():
                continue
            
            other_source = await self.detector.get_cached(c.chain, c.address)
            if not other_source:
                continue
            
            # Source similarity using MinHash/LSH
            similarity = self._compute_similarity(source, other_source)
            
            if similarity >= threshold:
                similar.append(SimilarContract(
                    chain=c.chain,
                    address=c.address,
                    name=c.name,
                    similarity=similarity,
                    estimated_relations="fork" if similarity > 0.95 else "inspired_by",
                ))
        
        return sorted(similar, key=lambda x: x.similarity, reverse=True)
```

### 6.4 Predictive Vulnerability Mapping

```python
class PredictiveVulnerabilityMapper:
    """Prediksi lokasi vulnerability berdasarkan analisis statis ribuan kontrak."""
    
    def __init__(self):
        self.model = self._load_model()  # Trained on known vulnerabilities
    
    async def predict_vulnerable_functions(
        self, chain: str, address: str,
    ) -> list[FunctionRisk]:
        """Prediksi fungsi mana yang paling mungkin vulnerable."""
        
        source = await self.detector.get_cached(chain, address)
        if not source:
            return []
        
        # Extract features untuk setiap fungsi
        functions_features = []
        for func in self._extract_functions(source):
            features = self._extract_features(func)
            functions_features.append(features)
        
        # Predict
        if self.model:
            risks = self.model.predict_proba(functions_features)
        else:
            # Fallback: rule-based scoring
            risks = [self._rule_based_score(f) for f in functions_features]
        
        # Sort by risk
        results = []
        for func, risk in zip(functions_features, risks):
            results.append(FunctionRisk(
                function_name=func["name"],
                risk_score=float(risk[1]) if hasattr(risk, '__iter__') else risk,
                top_3_vulnerabilities=self._top_vulnerabilities(func),
                estimated_exploitability=func["exploitability"],
                recommended_scan_tool=self._recommend_tool(func),
            ))
        
        return sorted(results, key=lambda x: x.risk_score, reverse=True)
    
    def _rule_based_score(self, func: dict) -> float:
        """Rule-based risk scoring."""
        score = 0.0
        
        # External calls
        if func["has_external_call"]: score += 0.3
        if func["has_delegatecall"]:  score += 0.5
        if func["has_transfer"]:      score += 0.2
        
        # State mutations
        if func["writes_state"]:      score += 0.2
        if func["uses_assembly"]:     score += 0.3
        if func["uses_unchecked"]:    score += 0.2
        
        # Complexity
        if func["lines_of_code"] > 50:  score += 0.1
        if func["parameters"] > 5:      score += 0.1
        
        return min(score, 1.0)
```

### 6.5 New Endpoints Level 4

```python
@router.get("/contracts/{chain}/{address}/bytecode/history")
async def get_bytecode_history(chain: str, address: str):
    """History bytecode untuk kontrak."""
    pass

@router.post("/contracts/{chain}/{address}/reconstruct")
async def reconstruct_source(chain: str, address: str):
    """Rekonstruksi source dari bytecode (unverified contract)."""
    pass

@router.get("/contracts/{chain}/{address}/cross-chain")
async def get_cross_chain_siblings(chain: str, address: str):
    """Cari kontrak yang sama di chain lain."""
    pass

@router.get("/contracts/{chain}/{address}/predict-risks")
async def predict_contract_risks(chain: str, address: str):
    """Prediksi fungsi mana yang vulnerable."""
    pass

@router.get("/contracts/forks/{chain}/{address}")
async def find_contract_forks(chain: str, address: str):
    """Cari fork/salinan kontrak."""
    pass

@router.get("/stats/bytecode")
async def get_bytecode_stats():
    """Statistik bytecode repository."""
    pass
```

---

## 7. Roadmap

```
Minggu 1 (Foundation)          Minggu 3 (Autonomous)
┌────────────────┐            ┌────────────────┐
│ 10+ providers   │            │ Block monitor   │
│ PostgreSQL      │            │ Cache warming   │
│ Compiler verify │            │ Exploit integ   │
│ Batch fetch     │            │ New endpoints   │
└────────┬───────┘            └────────┬───────┘
         │                             │
         ▼                             ▼
Minggu 2 (Intelligence)       Minggu 4 (God-Tier)
┌────────────────┐            ┌────────────────┐
│ ABI extraction  │            │ Bytecode repo   │
│ Dependency graph│            │ AI reconstruct  │
│ Upgrade detect  │            │ Cross-chain     │
│ Enrichment      │            │ Predictive      │
└────────────────┘            └────────────────┘
```

### Effort Estimation

| Level | Story Points | Man-Days | Key Deliverables |
|-------|-------------|----------|------------------|
| Level 1 | 34 SP | 15-18 | 10+ providers, PostgreSQL, compiler verify |
| Level 2 | 55 SP | 25-30 | ABI extraction, dependency graph, upgrade detection |
| Level 3 | 55 SP | 25-30 | Block monitor, cache warming, auto-exploit |
| Level 4 | 89 SP | 40-50 | Bytecode repo, AI reconstruction, predictive |
| **Total** | **~233 SP** | **105-128** | |

---

> **Catatan**: Enhancement ini mengubah service 03 dari **simple source fetcher** menjadi **comprehensive blockchain data intelligence platform** yang tidak hanya menyediakan source code, tapi juga memverifikasi, menganalisis, memonitor, dan memprediksi.
