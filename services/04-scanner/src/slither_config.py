"""Re-export SlitherConfigBuilder from vyper_lib for backward compatibility.

This file previously contained a duplicate of vyper_lib.slither_config.
Now it simply re-exports from the centralized library.
"""

from vyper_lib.slither_config import (  # noqa: F401
    SlitherConfigBuilder,
    create_slither_config,
)
