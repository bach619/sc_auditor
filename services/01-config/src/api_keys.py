"""API Key management for internal service-to-service auth.

Setiap service punya unique API key. Saat service A call service B,
ia menyertakan header:
  X-API-Key: <service_api_key>
  X-Service-Name: <service_name>

Karena project personal, ini adalah OPTIONAL hardening —
keys bisa di-generate otomatis dan tidak perlu rotasi rutin.
"""

from __future__ import annotations

import os
import secrets

# Default keys — auto-generated, disimpan di file YAML config
# Override via Config Service → settings page
SERVICE_API_KEYS: dict[str, str] = {}


def generate_api_key() -> str:
    """Generate random 32-char hex API key."""
    return secrets.token_hex(16)


def get_or_create_key(service_name: str, storage_path: str = "") -> str:
    """Get existing key or generate + persist new one."""
    if service_name in SERVICE_API_KEYS:
        return SERVICE_API_KEYS[service_name]
    key = generate_api_key()
    SERVICE_API_KEYS[service_name] = key
    if storage_path:
        _persist_keys(storage_path)
    return key


def validate_service_api_key(key: str, service_name: str) -> bool:
    """Validate service API key.

    Returns True if key matches OR if API key auth is disabled.
    (Disabled = empty dict — dev mode no-auth.)
    """
    if not SERVICE_API_KEYS:
        return True  # API key auth disabled — dev mode
    expected = SERVICE_API_KEYS.get(service_name)
    if expected is None:
        return False
    return secrets.compare_digest(key, expected)


def _persist_keys(path: str) -> None:
    """Save keys to YAML file for persistence across restarts."""
    import yaml
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        yaml.dump({"api_keys": SERVICE_API_KEYS}, f)


def load_keys(path: str) -> None:
    """Load keys from YAML file."""
    import yaml
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
            SERVICE_API_KEYS.update(data.get("api_keys", {}))
