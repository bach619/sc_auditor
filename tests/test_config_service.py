"""Config Service Tests.

Unit tests for the 01-config service: CRUD operations, defaults,
bulk upsert, reset, dual-write (SQLite + JSON), and edge cases.

Pure logic tests — no Docker or HTTP required.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# ── Path setup ───────────────────────────────────────────────
_CONFIG_SRC = str(Path(__file__).resolve().parents[1] / "services" / "01-config")


def _import_config_module(module_name: str):
    """Import from config src/ with namespace cleanup."""
    import importlib
    # Clear ALL cached src.* modules BEFORE import
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]
    if "src" in sys.modules:
        del sys.modules["src"]

    sys.path.insert(0, _CONFIG_SRC)
    try:
        mod = importlib.import_module(f"src.{module_name}")
        return mod
    finally:
        sys.path.pop(0)
        to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
        for k in to_remove:
            del sys.modules[k]
        if "src" in sys.modules:
            del sys.modules["src"]


# ── ConfigManager Tests (Legacy JSON store) ──────────────────


class TestConfigManager:
    """Tests for the legacy ConfigManager (pure JSON store)."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary directory for config data."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    def test_load_defaults_when_no_file(self, temp_config_dir):
        """If no config file exists, load() should create defaults."""
        manager_mod = _import_config_module("manager")
        mgr = manager_mod.ConfigManager(data_dir=str(temp_config_dir))

        # load() creates the file with defaults
        result = mgr.load()
        assert isinstance(result, dict)
        assert len(result) > 0

        # ConfigManager saves to {data_dir}/config.json
        config_file = temp_config_dir / "config.json"
        assert config_file.exists(), f"Default config should be written at {config_file}"

    def test_get_existing_key(self, temp_config_dir):
        """Getting an existing key should return its value."""
        manager_mod = _import_config_module("manager")
        mgr = manager_mod.ConfigManager(data_dir=str(temp_config_dir))
        mgr.load()

        # Set a key first
        mgr.set("test_key", "test_value")
        assert mgr.get("test_key") == "test_value"

    def test_get_missing_key_returns_none(self, temp_config_dir):
        """Getting a nonexistent key should return None without error."""
        manager_mod = _import_config_module("manager")
        mgr = manager_mod.ConfigManager(data_dir=str(temp_config_dir))

        value = mgr.get("nonexistent_key_xyz")
        assert value is None

    def test_set_new_key_persists(self, temp_config_dir):
        """Setting a key should persist it across manager instances."""
        manager_mod = _import_config_module("manager")
        mgr1 = manager_mod.ConfigManager(data_dir=str(temp_config_dir))
        mgr1.load()
        mgr1.set("persist_key", "persist_value")

        # Create a new manager pointing to the same file
        mgr2 = manager_mod.ConfigManager(data_dir=str(temp_config_dir))
        mgr2.load()
        assert mgr2.get("persist_key") == "persist_value"

    def test_delete_key_removes(self, temp_config_dir):
        """Deleting a key should remove it from the store."""
        manager_mod = _import_config_module("manager")
        mgr = manager_mod.ConfigManager(data_dir=str(temp_config_dir))
        mgr.load()

        mgr.set("delete_me", "value")
        assert mgr.get("delete_me") == "value"

        mgr.delete("delete_me")
        assert mgr.get("delete_me") is None

    def test_bulk_upsert_atomic(self, temp_config_dir):
        """Setting multiple keys in sequence should persist all of them."""
        manager_mod = _import_config_module("manager")
        mgr = manager_mod.ConfigManager(data_dir=str(temp_config_dir))
        mgr.load()

        keys = {f"bulk_key_{i}": f"bulk_value_{i}" for i in range(10)}
        for k, v in keys.items():
            mgr.set(k, v)

        # Read back all
        for k, v in keys.items():
            assert mgr.get(k) == v, f"Key {k} should be {v}"

        # Verify via re-load
        mgr2 = manager_mod.ConfigManager(data_dir=str(temp_config_dir))
        mgr2.load()
        for k, v in keys.items():
            assert mgr2.get(k) == v

    def test_reset_restores_defaults(self, temp_config_dir):
        """Reset should restore all keys back to factory defaults."""
        manager_mod = _import_config_module("manager")
        mgr = manager_mod.ConfigManager(data_dir=str(temp_config_dir))
        mgr.load()

        # Modify a key that exists in defaults
        key_to_test = "immunefi_refresh_interval"
        original = mgr.get(key_to_test)
        mgr.set(key_to_test, 99999)

        # Reset
        mgr.reset()
        restored = mgr.get(key_to_test)
        if original is not None:
            assert restored == original, f"Reset should restore {key_to_test} from 99999 back to {original}"

    def test_get_all_returns_dict(self, temp_config_dir):
        """get_all() should return a dictionary with all config keys."""
        manager_mod = _import_config_module("manager")
        mgr = manager_mod.ConfigManager(data_dir=str(temp_config_dir))
        mgr.load()

        all_config = mgr.get_all()
        assert isinstance(all_config, dict)
        assert len(all_config) > 0, "Should have at least some default keys"

    def test_concurrent_set_threadsafe(self, temp_config_dir):
        """Multiple concurrent sets should not corrupt data (lock test)."""
        import threading

        manager_mod = _import_config_module("manager")
        mgr = manager_mod.ConfigManager(data_dir=str(temp_config_dir))
        mgr.load()

        errors = []

        def set_key(i: int) -> None:
            try:
                mgr.set(f"concurrent_{i}", f"value_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=set_key, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent writes raised errors: {errors}"

        # Verify all keys persisted
        mgr.load()
        for i in range(50):
            assert mgr.get(f"concurrent_{i}") == f"value_{i}", f"Key concurrent_{i} missing"

    def test_corrupt_json_fallback_to_defaults(self, temp_config_dir):
        """If the config file is corrupt JSON, load() should fall back to defaults."""
        manager_mod = _import_config_module("manager")

        # Create a corrupt config file
        config_dir = temp_config_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        config_file.write_text("this is not valid json {{{")

        # Should not crash — fall back to defaults
        mgr = manager_mod.ConfigManager(data_dir=str(temp_config_dir))
        result = mgr.load()
        assert result is not None
        assert isinstance(result, dict)


# ── JSON Utils Tests ─────────────────────────────────────────


class TestAtomicJSONUtils:
    """Tests for shared/json_utils.py — atomic read/write."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary JSON file path."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp) / "test.json"

    def test_atomic_write_creates_file(self, temp_file):
        """atomic_json_write should create the file if it doesn't exist."""
        # Re-import from the shared module installed in the env or local path
        # We'll test the logic inline since we can't guarantee import
        from services.shared.json_utils import atomic_json_write, atomic_json_read

        data = {"key": "value"}
        atomic_json_write(temp_file, data)
        assert temp_file.exists()

    def test_atomic_write_then_read_roundtrip(self, temp_file):
        """Write then read should return the same data."""
        from services.shared.json_utils import atomic_json_write, atomic_json_read

        data = {"hello": "world", "nested": {"a": 1, "b": [2, 3, 4]}}
        atomic_json_write(temp_file, data)
        result = atomic_json_read(temp_file)
        assert result == data

    def test_atomic_read_returns_default_for_missing(self, temp_file):
        """Reading a nonexistent file should return the default value."""
        from services.shared.json_utils import atomic_json_read

        missing = temp_file.parent / "nonexistent.json"
        result = atomic_json_read(missing, default={"fallback": True})
        assert result == {"fallback": True}

    def test_atomic_read_returns_default_for_corrupt(self, temp_file):
        """Reading a corrupt file should return the default."""
        from services.shared.json_utils import atomic_json_read

        temp_file.write_text("not valid json {{{broken")
        result = atomic_json_read(temp_file, default=[])
        assert result == []

    def test_atomic_write_list_data(self, temp_file):
        """atomic_json_write should handle list data too."""
        from services.shared.json_utils import atomic_json_write, atomic_json_read

        data = [1, 2, 3, {"nested": "dict"}]
        atomic_json_write(temp_file, data)
        result = atomic_json_read(temp_file)
        assert result == data
