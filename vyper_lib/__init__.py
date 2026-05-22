"""Vyper Shared Library — Common utilities, models, and tools for all services."""

from vyper_lib.models import (
    ApiResponse,
    Finding,
    ForgeResult,
    HealthData,
    InstallResult,
    Meta,
    ScanRequest,
    ScanResponse,
    ToolInfo,
    ToolResult,
)
from vyper_lib.solc_manager import SolcManager, create_solc_manager
from vyper_lib.deps import DependencyResolver, create_dependency_resolver
from vyper_lib.slither_config import SlitherConfigBuilder, create_slither_config
from vyper_lib.utils import read_json, write_json, parse_standard_input_json
from vyper_lib.config_client import ConfigClient, _get_shared_client

__version__ = "0.1.0"

__all__ = [
    "ApiResponse",
    "ConfigClient",
    "DependencyResolver",
    "Finding",
    "ForgeResult",
    "HealthData",
    "InstallResult",
    "Meta",
    "ScanRequest",
    "ScanResponse",
    "SlitherConfigBuilder",
    "SolcManager",
    "ToolInfo",
    "ToolResult",
    "create_dependency_resolver",
    "create_slither_config",
    "create_solc_manager",
    "parse_standard_input_json",
    "read_json",
    "write_json",
]
