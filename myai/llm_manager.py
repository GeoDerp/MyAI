"""Public LLM manager shim.

This module delegates to the implementation in _llm_manager_impl so the
public import path is stable and the implementation can be replaced
atomically.
"""

from ._llm_manager_impl import LLMManager, LLMError, call_llm_with_retries

__all__ = ["LLMManager", "LLMError", "call_llm_with_retries"]
