"""Re-export SolcManager from vyper_lib for backward compatibility.

This file previously contained a duplicate of vyper_lib.solc_manager.
Now it simply re-exports from the centralized library.
"""

from vyper_lib.solc_manager import (  # noqa: F401
    SolcManager,
    create_solc_manager,
)
