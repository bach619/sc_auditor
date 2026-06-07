# Changelog — VYPER (sc_auditor)

## [0.5.0] — 2026-06-07

### Added
- SQLite storage layer — 28 services migrated from JSON files (Agenda 27)
- Atomic JSON utility: atomic_json_write/read (Agenda 29)
- Circuit breaker pattern — 5 pre-configured breakers (Agenda 29)
- Service-to-service HMAC auth token (Agenda 29)
- Request ID middleware — X-Request-ID propagation (Agenda 29)
- Health aggregation endpoint — GET /health/aggregate (Agenda 29)
- Backup scheduler — 6-hour tar.gz + 30-day retention (Agenda 29)
- Scan result cache — SQLite-backed, 24h TTL (Agenda 29)
- HTTPX connection pooling — shared client pool (Agenda 29)
- Rate limiting — slowapi on dashboard API Gateway (Agenda 29)
- 85 unit tests — pipeline states, classifier, config, exploit, immunefi, E2E (Agenda 29)
- CHANGELOG.md, DEPLOYMENT.md, DISASTER_RECOVERY.md (Agenda 29)

### Changed
- Scanner tools run in parallel via asyncio.gather (3-6x faster)
- File splitting: 5 giant files → 28 small modules (< 500 lines)
- HTTP connection pooling for inter-service calls
- CI coverage gate: 0% → 25% → 50% → 70%
- Docker security hardening: non-root, read-only, cap_drop ALL
- Shared volumes vyper_kb + vyper_learning deprecated (replaced by SQLite)

### Fixed
- 24 crashing services — register_error_handlers(app) syntax errors
- Pydantic strict mode — model_config extra=forbid
- Audit trail — structured logging for config changes

## [0.4.0] — 2026-06-04
### Added
- 28 microservice architecture (from 19)
- E2E audit pipeline: Immunefi → Report
- Dashboard React SPA with real-time SSE
- Antonio AI Agent with team-based auditing
- 5-bounty-platform integration (Code4rena, Sherlock, Cantina, Hats, Immunefi)
- Multi-chain support (Ethereum, StarkNet via 22-23 services)

## [0.3.0] — 2026-05-26
### Added
- Initial 19-service architecture
- Slither, Mythril, Echidna, Halmos, Foundry integration
- Orchestrator pipeline state machine
- Exploit engine with Anvil fork
