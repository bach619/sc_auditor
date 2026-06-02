"""pytest configuration for 04b-scanner-echidna unit tests.

Adds the service source path so that ``from src.intelligence.*`` imports work.
"""

import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[2] / "services" / "04b-scanner-echidna"

if SERVICE_DIR.exists() and str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))
