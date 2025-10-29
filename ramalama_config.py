"""
Backwards-compatible shim for `ramalama_config` expected by tests.
Re-exports from `myai.ramalama_config`.
"""
from myai.ramalama_config import *  # noqa: F401,F403

__all__ = getattr(__import__("myai.ramalama_config", fromlist=["*"]), "__all__", [])
