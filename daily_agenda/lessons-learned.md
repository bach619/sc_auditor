# Lessons Learned — sc_auditor

## Agenda 14: Custom Slither Detectors Engine

### Technical Insights
1. **Slither's Python API vs CLI**: Custom detectors require using Slither's Python API (`from slither import Slither`) rather than the CLI. The CLI `--detect` flag only supports built-in detectors.
2. **Sandboxing via exec()**: Python's `exec()` with restricted globals is sufficient for a local-first tool, but not production-grade sandboxing. For multi-tenant scenarios, subprocess or container isolation would be needed.
3. **AbstractDetector interface**: Slither's `AbstractDetector` expects `detect()` to return a list of `Result` objects from `self.generate_result()`, not raw dicts. The example detectors use the proper interface.

### Process Improvements
1. **Handoff contract effectiveness**: The detailed handoff contract (with code templates and exact file paths) made vibe-coder execution smooth with zero rework needed.
2. **Phase separation**: Building core engine (Phase 1) before API layer (Phase 2) caught import issues early.
3. **Test-first for sandbox**: Writing security tests alongside the sandbox implementation helped validate edge cases.

### Technical Debt to Track
- Slither must be importable as a Python package in the Docker image (currently only installed as CLI tool)
- Custom detector `import` sandbox can be bypassed by determined attackers — acceptable for local use
- Frontend DetectorManager uses direct fetch() instead of a shared API client
