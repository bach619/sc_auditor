"""Configuration for the Orchestrator Service."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ORCHESTRATOR_",
        case_sensitive=False,
    )

    # --- Service Identity ---
    service_name: str = "orchestrator"
    host: str = "0.0.0.0"
    port: int = 8009
    log_level: str = "INFO"

    # --- Upstream Service URLs (Docker internal ports) ---
    immunefi_url: str = "http://02-immunefi:8000"
    source_url: str = "http://03-source:8000"
    scanner_url: str = "http://04-scanner:8000"
    scanner_slither_url: str = "http://04a-scanner-slither:8014"
    scanner_echidna_url: str = "http://04b-scanner-echidna:8015"
    scanner_forge_url: str = "http://04c-scanner-forge:8016"
    scanner_halmos_url: str = "http://04d-scanner-halmos:8017"
    mythril_url: str = "http://05-scanner-mythril:8013"
    ai_url: str = "http://06-ai:8000"
    classifier_url: str = "http://07-classifier:8000"
    exploit_url: str = "http://08-exploit:8006"
    reporter_url: str = "http://09-reporter:8007"
    notifier_url: str = "http://10-notifier:8000"
    upkeep_url: str = "http://13-upkeep:8000"
    dashboard_url: str = "http://15-dashboard:8000"

    # --- Data Persistence ---
    data_dir: str = "/data/orchestrator"

    # --- Pipeline Timing ---
    step_timeout_seconds: int = 1800  # 30 min per step
    pipeline_global_timeout_seconds: int = 14400  # 4 h global max
    retry_max_attempts: int = 3
    retry_base_delay_seconds: float = 2.0
    retry_max_delay_seconds: float = 60.0

    # --- Daemon ---
    daemon_interval_minutes: int = 60
    daemon_batch_size: int = 3

    # --- Priority Scoring Weights ---
    priority_weight_bounty: float = 0.40
    priority_weight_similarity: float = 0.30
    priority_weight_chain: float = 0.15
    priority_weight_freshness: float = 0.10
    priority_weight_tp_history: float = 0.05

    # --- Resource Governance ---
    max_concurrent_scans: int = 2
    max_concurrent_ai: int = 1

    # --- Batch / Debounce ---
    debounce_hours: int = 24
    batch_default_size: int = 5

    # --- Similarity ---
    similarity_threshold: float = 0.7

    # --- Paths (relative to data_dir) ---
    audit_log_path: str = "audit_log.json"
    queue_path: str = "queue.json"
    similarity_path: str = "similarity.json"
    daemon_state_path: str = "daemon_state.json"
    stats_path: str = "stats.json"

    # --- Derived properties ---
    @property
    def audit_log_file(self) -> Path:
        return Path(self.data_dir) / self.audit_log_path

    @property
    def queue_file(self) -> Path:
        return Path(self.data_dir) / self.queue_path

    @property
    def similarity_file(self) -> Path:
        return Path(self.data_dir) / self.similarity_path

    @property
    def daemon_state_file(self) -> Path:
        return Path(self.data_dir) / self.daemon_state_path

    @property
    def stats_file(self) -> Path:
        return Path(self.data_dir) / self.stats_path


# Global singleton
config: Final[OrchestratorConfig] = OrchestratorConfig()
