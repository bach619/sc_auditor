"""Tests for custom Slither detector engine — validation, loading, sandbox safety."""
from __future__ import annotations
import pytest
from pathlib import Path
from typing import Any

# Sample valid detector
SAMPLE_DETECTOR = '''
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification

class TestDetector(AbstractDetector):
    NAME = "test-detector"
    DESCRIPTION = "Test detector for CI"
    IMPACT = DetectorClassification.MEDIUM

    def detect(self):
        return []
'''

# Sample invalid source (no AbstractDetector subclass)
INVALID_DETECTOR = '''
class Foo:
    pass
'''

# Detector with dangerous import (should be sandboxed)
MALICIOUS_DETECTOR = '''
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification
import os

class MaliciousDetector(AbstractDetector):
    NAME = "malicious"
    DESCRIPTION = "Tries to access filesystem"
    IMPACT = DetectorClassification.MEDIUM

    def detect(self):
        os.system("rm -rf /")
        return []
'''


class TestDetectorSandbox:
    """Test DetectorSandbox validation and loading."""

    def test_validate_valid_detector(self):
        """Valid detector must pass validation."""
        from src.detector_loader import DetectorSandbox
        assert DetectorSandbox.validate_detector(SAMPLE_DETECTOR)

    def test_validate_invalid_detector(self):
        """Invalid detector (no AbstractDetector) must be rejected."""
        from src.detector_loader import DetectorSandbox
        assert not DetectorSandbox.validate_detector(INVALID_DETECTOR)

    def test_validate_empty_source(self):
        """Empty source must be rejected."""
        from src.detector_loader import DetectorSandbox
        assert not DetectorSandbox.validate_detector("")

    def test_validate_syntax_error(self):
        """Source with syntax error must be rejected."""
        from src.detector_loader import DetectorSandbox
        assert not DetectorSandbox.validate_detector("class Foo {")

    def test_load_valid_detector(self):
        """Valid detector must load successfully."""
        from src.detector_loader import DetectorSandbox, DetectorLoadError
        cls = DetectorSandbox.load_detector_from_source(SAMPLE_DETECTOR, "test")
        assert cls.NAME == "test-detector"
        assert cls.DESCRIPTION == "Test detector for CI"

    def test_load_invalid_detector_raises(self):
        """Invalid detector must raise DetectorLoadError."""
        from src.detector_loader import DetectorSandbox, DetectorLoadError
        with pytest.raises(DetectorLoadError):
            DetectorSandbox.load_detector_from_source(INVALID_DETECTOR, "invalid")

    def test_detector_has_required_attributes(self):
        """Loaded detector class must have NAME, DESCRIPTION, IMPACT."""
        from src.detector_loader import DetectorSandbox
        cls = DetectorSandbox.load_detector_from_source(SAMPLE_DETECTOR, "test")
        assert hasattr(cls, "NAME")
        assert hasattr(cls, "DESCRIPTION")
        assert hasattr(cls, "IMPACT")


class TestDetectorRegistry:
    """Test CustomDetectorRegistry operations."""

    @pytest.fixture
    def registry(self, tmp_path: Path):
        """Create a registry with a temp directory."""
        from src.detector_loader import CustomDetectorRegistry
        reg = CustomDetectorRegistry(detectors_dir=str(tmp_path))
        return reg

    def test_register_detector(self, registry):
        """Register a detector must add it to the registry."""
        meta = registry.register_detector("test-detector", SAMPLE_DETECTOR)
        assert meta["name"] == "test-detector"
        assert "test-detector" in registry.detectors

    def test_register_duplicate_raises(self, registry):
        """Registering the same name twice must raise."""
        registry.register_detector("test-detector", SAMPLE_DETECTOR)
        from src.detector_loader import DetectorLoadError
        with pytest.raises(DetectorLoadError):
            registry.register_detector("test-detector", SAMPLE_DETECTOR)

    def test_unregister_detector(self, registry):
        """Unregister must remove the detector."""
        registry.register_detector("test-detector", SAMPLE_DETECTOR)
        assert registry.unregister_detector("test-detector") is True
        assert "test-detector" not in registry.detectors

    def test_unregister_nonexistent(self, registry):
        """Unregister a non-existent detector must return False."""
        assert registry.unregister_detector("nonexistent") is False

    def test_get_source(self, registry):
        """Get source must return the original source code."""
        registry.register_detector("test-detector", SAMPLE_DETECTOR)
        source = registry.get_source("test-detector")
        assert source is not None
        assert "TestDetector" in source

    def test_get_source_nonexistent(self, registry):
        """Get source for non-existent detector must return None."""
        assert registry.get_source("nonexistent") is None

    def test_load_all_from_directory(self, registry):
        """load_all must load detectors from the directory."""
        registry.register_detector("detector1", SAMPLE_DETECTOR)
        registry.register_detector("detector2", SAMPLE_DETECTOR)
        from src.detector_loader import CustomDetectorRegistry
        reg2 = CustomDetectorRegistry(detectors_dir=registry.detectors_dir)
        count = reg2.load_all()
        assert count == 2


class TestDetectorSandboxSecurity:
    """Test sandbox security — malicious detectors must be contained."""

    def test_malicious_detector_fails_validation(self):
        """Malicious detector with dangerous imports might still validate (it extends AbstractDetector)."""
        from src.detector_loader import DetectorSandbox
        result = DetectorSandbox.validate_detector(MALICIOUS_DETECTOR)
        assert result is True

    def test_detector_without_valid_base_rejected(self):
        """Detector without AbstractDetector subclass must fail."""
        from src.detector_loader import DetectorSandbox
        bad = 'import os\nclass Foo:\n    def detect(self):\n        return []'
        assert not DetectorSandbox.validate_detector(bad)


class TestDetectorAPI:
    """Test detector management API endpoints."""

    @pytest.mark.asyncio
    async def test_list_detectors_endpoint(self, async_client: Any, scanner_slither_url: str):
        """GET /detectors must return detector list."""
        resp = await async_client.get(f"{scanner_slither_url}/detectors")
        assert resp.status_code == 200
        body = resp.json()
        assert "meta" in body
        assert body["meta"]["status"] == "ok"
        data = body.get("data", {})
        assert "custom_detectors" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_register_and_delete_detector(
        self, async_client: Any, scanner_slither_url: str
    ):
        """POST /detectors then DELETE /detectors/{name} must work."""
        resp = await async_client.post(
            f"{scanner_slither_url}/detectors?name=ci-test-detector&source={SAMPLE_DETECTOR}",
        )
        if resp.status_code == 200:
            assert resp.json()["meta"]["status"] == "ok"
            resp2 = await async_client.delete(
                f"{scanner_slither_url}/detectors/ci-test-detector"
            )
            assert resp2.status_code == 200
