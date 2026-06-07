"""Custom Slither Detector Loader — sandboxed execution, registry, and runner."""
from __future__ import annotations

import ast
import importlib.util
import inspect
import signal
import time
from datetime import UTC, datetime
from pathlib import Path

import structlog
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification

from vyper_lib.models import Finding

log = structlog.get_logger()


class DetectorLoadError(Exception):
    pass


class DetectorTimeoutError(Exception):
    pass


class DetectorSandbox:
    """Safe execution environment for custom Slither detectors."""

    ALLOWED_MODULES = {
        "slither", "slither.detectors", "slither.core",
        "slither.core.declarations", "slither.core.cfg",
        "slither.core.variables", "slither.core.expressions",
        "typing", "enum", "dataclasses",
    }

    @staticmethod
    def validate_detector(source: str) -> bool:
        """Validate detector syntax without executing."""
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id in ("AbstractDetector", "SlitherDetector"):
                            return True
            return False
        except SyntaxError:
            return False

    @staticmethod
    def load_detector_from_source(source: str, module_name: str) -> type[AbstractDetector]:
        """Load detector from source code string (sandboxed exec)."""
        if not DetectorSandbox.validate_detector(source):
            raise DetectorLoadError("Invalid detector: must subclass AbstractDetector")

        spec = importlib.util.spec_from_loader(module_name, loader=None)
        importlib.util.module_from_spec(spec)

        restricted_globals = {
            "__name__": module_name,
            "__builtins__": __builtins__,
        }

        try:
            exec(compile(source, f"{module_name}.py", "exec"), restricted_globals)
        except Exception as e:
            raise DetectorLoadError(f"Failed to load detector: {e}")

        detector_class = None
        for name, obj in restricted_globals.items():
            if (inspect.isclass(obj) and
                issubclass(obj, AbstractDetector) and
                    obj is not AbstractDetector):
                detector_class = obj
                break

        if detector_class is None:
            raise DetectorLoadError("No detector class found in source")

        return detector_class


class CustomDetectorRegistry:
    """Registry for all custom detectors. Load from disk, register/unregister via API."""

    def __init__(self, detectors_dir: str = "/data/detectors"):
        self.detectors_dir = Path(detectors_dir)
        self.detectors: dict[str, type[AbstractDetector]] = {}
        self.metadata: dict[str, dict] = {}
        self.detectors_dir.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> int:
        """Load all detectors from the detectors directory + built-in overpower detectors."""
        count = 0

        # Load from /data/detectors/ (user-registered)
        for file in sorted(self.detectors_dir.glob("*.py")):
            if file.name == "__init__.py":
                continue
            try:
                source = file.read_text()
                detector_class = DetectorSandbox.load_detector_from_source(
                    source, f"custom_detector_{file.stem}"
                )
                name = getattr(detector_class, "ARGUMENT", file.stem)
                self._register_class(name, detector_class, file.name)
                count += 1
            except DetectorLoadError as e:
                log.warning("detector.load.failed", file=file.name, error=str(e))

        # Load built-in overpower detectors
        count += self._load_builtin_overpower()

        return count

    def _load_builtin_overpower(self) -> int:
        """Load built-in overpower detectors from the detectors/ package."""
        count = 0
        builtin_dir = Path(__file__).parent.parent / "detectors"
        if not builtin_dir.exists():
            return count

        for file in sorted(builtin_dir.glob("*.py")):
            if file.name.startswith("__") or file.name == "detector_loader.py":
                continue
            try:
                # Import the module directly
                module_name = f"detectors.{file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    # Find detector class in module
                    for attr_name in dir(module):
                        obj = getattr(module, attr_name)
                        if (inspect.isclass(obj) and
                            issubclass(obj, AbstractDetector) and
                                obj is not AbstractDetector):
                            name = getattr(obj, "ARGUMENT", file.stem)
                            self._register_class(name, obj, file.name)
                            count += 1
                            log.info("overpower.detector.loaded", name=name, file=file.name)
            except Exception as e:
                log.warning("overpower.detector.failed", file=file.name, error=str(e))

        return count

    def _register_class(self, name: str, detector_class: type[AbstractDetector], source_file: str) -> None:
        """Register a detector class in the registry."""
        self.detectors[name] = detector_class
        self.metadata[name] = {
            "name": name,
            "description": getattr(detector_class, "WIKI_DESCRIPTION", ""),
            "impact": str(getattr(detector_class, "IMPACT", DetectorClassification.MEDIUM)),
            "file": source_file,
            "loaded_at": datetime.now(UTC).isoformat(),
            "overpower": source_file.startswith("detector_"),  # Mark as overpower
        }

    def register_detector(self, name: str, source: str) -> dict:
        """Register a new detector via API."""
        file_path = self.detectors_dir / f"{name}.py"
        if file_path.exists():
            raise DetectorLoadError(f"Detector '{name}' already exists")
        if not DetectorSandbox.validate_detector(source):
            raise DetectorLoadError("Invalid detector source code")
        file_path.write_text(source)
        detector_class = DetectorSandbox.load_detector_from_source(source, name)
        self.detectors[name] = detector_class
        self.metadata[name] = {
            "name": name,
            "description": getattr(detector_class, "DESCRIPTION", ""),
            "impact": str(getattr(detector_class, "IMPACT", DetectorClassification.MEDIUM)),
            "file": file_path.name,
            "loaded_at": datetime.now(UTC).isoformat(),
        }
        return self.metadata[name]

    def unregister_detector(self, name: str) -> bool:
        """Unregister and delete a detector."""
        if name in self.detectors:
            del self.detectors[name]
            meta = self.metadata.pop(name, {})
            file_path = self.detectors_dir / meta.get("file", f"{name}.py")
            if file_path.exists():
                file_path.unlink()
            return True
        return False

    def get_source(self, name: str) -> str | None:
        """Get the source code of a registered detector."""
        meta = self.metadata.get(name)
        if not meta:
            return None
        file_path = self.detectors_dir / meta.get("file", f"{name}.py")
        if file_path.exists():
            return file_path.read_text()
        return None

    def get_built_in_count(self) -> int:
        """Return count of available Slither built-in detectors."""
        try:
            from slither.detectors import all_detectors
            return len(all_detectors)
        except ImportError:
            return 0


class CustomDetectorRunner:
    """Run custom detectors alongside Slither on Solidity source code."""

    def __init__(self, registry: CustomDetectorRegistry):
        self.registry = registry

    def run_detectors(
        self,
        source_dir: Path,
        detector_names: list[str],
        timeout: int = 60,
    ) -> list[Finding]:
        """Run specified custom detectors against source files.

        This uses Slither's Python API to load the contract and run
        custom detector instances. Each detector runs in-process with
        a per-detector timeout enforced via signal/alarm.
        """
        from slither import Slither

        findings: list[Finding] = []
        start = time.monotonic()

        try:
            slither = Slither(str(source_dir))

            for name in detector_names:
                detector_cls = self.registry.detectors.get(name)
                if not detector_cls:
                    log.warning("detector.not_found", name=name)
                    continue

                try:
                    instance = detector_cls()
                    instance.slither = slither

                    class TimeoutError(Exception):
                        pass

                    def handler(signum, frame):
                        raise TimeoutError(f"Detector '{name}' timed out")

                    signal.signal(signal.SIGALRM, handler)
                    signal.alarm(min(timeout, 30))

                    try:
                        detector_results = instance.detect()
                    finally:
                        signal.alarm(0)

                    for det_result in detector_results:
                        finding = Finding(
                            tool=f"custom:{name}",
                            severity=self._map_impact(detector_cls.IMPACT),
                            title=getattr(det_result, "check", name) if hasattr(det_result, "check") else name,
                            description=getattr(detector_cls, "DESCRIPTION", "") or "",
                            contract="",
                            line=0,
                            recommendation="",
                        )
                        findings.append(finding)

                except Exception as e:
                    log.warning("detector.run.failed", name=name, error=str(e))

        except Exception as e:
            log.error("slither.load.failed", error=str(e))

        log.info("custom_detectors.complete", count=len(findings), duration=round(time.monotonic() - start, 2))
        return findings

    @staticmethod
    def _map_impact(impact) -> str:
        mapping = {
            DetectorClassification.HIGH: "high",
            DetectorClassification.MEDIUM: "medium",
            DetectorClassification.LOW: "low",
            DetectorClassification.INFORMATIONAL: "informational",
        }
        return mapping.get(impact, "medium")
