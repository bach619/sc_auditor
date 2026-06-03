"""Re-export DependencyResolver from vyper_lib for backward compatibility.

This file previously contained a duplicate of vyper_lib.deps.
Now it simply re-exports from the centralized library.
"""

from vyper_lib.deps import (  # noqa: F401
    DependencyResolver,
    create_dependency_resolver,
)
