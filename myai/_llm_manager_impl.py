"""Internal LLM manager implementation.

This file contains the real implementation. Other modules should import
via `myai.llm_manager` which delegates into this file. Keeping the
implementation separate makes atomic replacement simpler.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, Optional, Iterator
from datetime import datetime
from collections.abc import Mapping

logger = logging.getLogger("myai.llm.impl")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(h)
    logger.setLevel(os.environ.get("MYAI_LOG_LEVEL", "INFO"))


class LLMError(Exception):
    """Exception raised for LLM-related errors.
    
    Attributes:
        code: Error code (e.g., 'timeout', '4xx', '5xx', 'connection')
        message: Human-readable error message
        partial: Partially captured response text (if any)
    """
    
    def __init__(self, message: str, code: str = 'unknown', partial: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.partial = partial


def save_partial_output(partial: str, prefix: str = 'partial_llm') -> str:
    """Save partial LLM output to disk for debugging."""
    try:
        partial_dir = os.environ.get('MYAI_PARTIAL_DIR', '/tmp')
        os.makedirs(partial_dir, exist_ok=True)
        
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        filename = os.path.join(partial_dir, f'{prefix}_{timestamp}.txt')
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(partial)
        
        logger.info(f'Saved partial LLM output to {filename}')
        return filename
    except Exception as e:
        logger.warning(f'Failed to save partial output: {e}')
        return ''


class LLMManager:
    """Clean, minimal LLM manager implementation."""

    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("LITELLM_API_KEY")
        self.base_url = base_url or os.environ.get("LITELLM_BASE_URL")
        self._debug_file = os.environ.get("MYAI_DEBUG_FILE")

    def _write_debug(self, text: str) -> None:
        if not self._debug_file:
            return
        try:
            with open(self._debug_file, "a") as fh:
                fh.write(text)
        except Exception:
            logger.debug("Failed to write debug file %s", self._debug_file)

    def _completion_stub(self, *, stream: bool = False, **kwargs: Any):
        if stream:
            return iter(())
        return {"choices": [{"message": {"content": "[stub]"}}]}

    def _get_completion_callable(self):
        try:
            from litellm import completion  # type: ignore

            return completion
        except Exception:
            return self._completion_stub

    def get_completion(self, messages: list[Dict[str, str]], **kwargs: Any) -> Optional[Dict[str, Any]]:
        """Get completion with automatic retry logic."""
        retries = int(os.environ.get('LLM_RETRIES', '2'))
        timeout = int(os.environ.get('LLM_TIMEOUT', '120'))  # Increased default from 30 to 120
        
        return self._get_completion_with_retries(
            messages=messages,
            retries=retries,
            timeout=timeout,
            **kwargs
        )
    
    def _get_completion_with_retries(
        self,
        messages: list[Dict[str, str]],
        retries: int = 2,
        timeout: int = 30,
        **kwargs: Any
    ) -> Optional[Dict[str, Any]]:
        """Internal method with retry logic."""
        fn = self._get_completion_callable()
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                if attempt > 0:
                    sleep_time = 0.5 * (2 ** (attempt - 1))
                    logger.info(f'LLM retry attempt {attempt}/{retries}, sleeping {sleep_time}s')
                    time.sleep(sleep_time)
                
                res = fn(
                    model=self.model,
                    messages=messages,
                    api_key=self.api_key,
                    api_base=self.base_url,
                    timeout=timeout,
                    **kwargs
                )
                self._write_debug(repr(res) + "\n")
                return res
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if it's a retryable error
                is_retryable = (
                    'timeout' in error_str or
                    'connection' in error_str or
                    '5' in error_str or  # 5xx errors
                    'rate' in error_str
                )
                
                if not is_retryable or attempt >= retries:
                    logger.exception(f"get_completion failed after {attempt + 1} attempts")
                    return None
                else:
                    logger.warning(f"Retryable error on attempt {attempt + 1}: {e}")
        
        logger.error(f"Max retries exhausted. Last error: {last_error}")
        return None

    def get_streaming_completion(self, messages: list[Dict[str, str]], **kwargs: Any) -> Optional[Iterator[Any]]:
        fn = self._get_completion_callable()
        try:
            return fn(model=self.model, messages=messages, api_key=self.api_key, api_base=self.base_url, stream=True, **kwargs)
        except Exception:
            logger.exception("get_streaming_completion failed")
            return None

    def _to_mapping(self, value: Any) -> Optional[Mapping[str, Any]]:
        """Best-effort conversion of model/namespace objects to plain mappings."""
        if isinstance(value, Mapping):
            return value
        for attr in ("model_dump", "dict"):
            if hasattr(value, attr):
                try:
                    data = getattr(value, attr)()
                    if isinstance(data, Mapping):
                        return data
                except Exception:
                    continue
        return None

    def _extract_content(self, node: Any) -> str:
        """Extract textual content from message/delta payloads."""
        if not node:
            return ""
        if isinstance(node, str):
            return node
        if isinstance(node, list):
            parts = [self._extract_content(part) for part in node]
            combined = "".join(part for part in parts if part)
            return combined
        mapping = self._to_mapping(node)
        if mapping:
            for key in ("content", "text"):
                if key in mapping:
                    extracted = self._extract_content(mapping[key])
                    if extracted:
                        return extracted
        for attr in ("content", "text"):
            if hasattr(node, attr):
                extracted = self._extract_content(getattr(node, attr))
                if extracted:
                    return extracted
        return ""

    def extract_assistant_text(self, response: Optional[Dict[str, Any]]) -> str:
        if not response:
            return ""
        if isinstance(response, str):
            return response

        payload = self._to_mapping(response)
        choices = None
        if payload:
            choices = payload.get("choices")
        if not choices and hasattr(response, "choices"):
            choices = getattr(response, "choices")
        if not choices:
            return ""

        first_choice = choices[0]
        choice_map = self._to_mapping(first_choice) or {}

        for key in ("message", "delta", "content"):
            candidate = choice_map.get(key) or getattr(first_choice, key, None)
            text = self._extract_content(candidate)
            if text:
                return text

        if isinstance(first_choice, str):
            return first_choice

        return ""

    def extract_assistant_json(self, response: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        text = self.extract_assistant_text(response)
        if not text:
            return None
        try:
            import json

            o = json.loads(text)
            if isinstance(o, dict):
                return o
        except Exception:
            return None

    def set_base_url(self, base_url: Optional[str]) -> bool:
        self.base_url = base_url
        return bool(self.base_url)


class LLMError(Exception):
    """Structured error for LLM failures.

    Attributes:
        code: short error code (e.g. '4xx', '5xx', 'connection')
        message: human-readable message
        partial: optional partial assistant text captured before failure
    """

    def __init__(self, code: str, message: str, partial: Optional[str] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.partial = partial


def call_llm_with_retries(
    manager: LLMManager,
    messages: list[dict],
    timeout: int = 30,
    retries: int = 2,
    backoff_factor: float = 0.5,
    model: Optional[str] = None,
    stream: bool = False,
) -> str:
    """Call the LLM via the provided manager with retries and basic backoff.

    On transient errors (5xx / exceptions) retry `retries` times with
    exponential backoff. Don't retry client (4xx) errors. If streaming is
    requested, attempt to consume available partials and persist them.

    Returns assistant text on success or raises LLMError on failure. Partial
    outputs (if any) are saved to MYAI_PARTIAL_DIR as `partial_llm_<ts>.txt`.
    """
    import time
    import json
    import datetime
    import os

    # Prefer explicit model override; otherwise use manager default
    if model:
        manager.model = model

    attempt = 0
    last_exc = None
    partial_text = None
    while attempt <= retries:
        try:
            if stream:
                it = manager.get_streaming_completion(messages, timeout=timeout)
                if it is None:
                    raise RuntimeError("streaming not available")
                # Consume iterator to build partial_text
                parts = []
                for chunk in it:
                    try:
                        # litellm streaming yields dicts or strings
                        if isinstance(chunk, dict):
                            # try to extract message content if present
                            content = None
                            if 'choices' in chunk and chunk['choices']:
                                content = chunk['choices'][0].get('delta') or chunk['choices'][0].get('message', {}).get('content')
                            elif 'content' in chunk:
                                content = chunk.get('content')
                            if content:
                                parts.append(str(content))
                        else:
                            parts.append(str(chunk))
                    except Exception:
                        # ignore malformed streaming chunk
                        continue
                partial_text = "".join(parts)
                # Return partial_text as the assistant output
                return partial_text or ""
            else:
                res = manager.get_completion(messages, timeout=timeout)
                # manager.get_completion returns None on internal failure
                if res is None:
                    raise RuntimeError("LLM manager returned None")
                # Extract assistant text
                text = manager.extract_assistant_text(res)
                return text or ""
        except Exception as e:
            last_exc = e
            # Determine whether error looks like a client (4xx) error by
            # checking attributes commonly set by HTTP clients
            code = getattr(e, 'status_code', None) or getattr(e, 'code', None)
            # If code looks like 4xx, raise immediately
            try:
                code_int = int(code) if code is not None else None
            except Exception:
                code_int = None

            if code_int is not None and 400 <= code_int < 500:
                raise LLMError(str(code_int), f"Client error calling LLM: {e}")

            # Transient/server error: retry unless we've exhausted attempts
            attempt += 1
            if attempt > retries:
                # Persist partial if present
                try:
                    partial_text = partial_text or ""
                    # Use timezone-aware UTC timestamps
                    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                    outdir = os.environ.get('MYAI_PARTIAL_DIR', '/tmp')
                    fname = os.path.join(outdir, f'partial_llm_{ts}.txt')
                    with open(fname, 'w') as fh:
                        fh.write(partial_text or f'Last exception: {repr(e)}\n')
                except Exception:
                    logger.debug('Failed to write partial llm output')
                raise LLMError('5xx', f'LLM call failed after {attempt} attempts: {e}', partial=partial_text)

            sleep_for = backoff_factor * (2 ** (attempt - 1))
            time.sleep(sleep_for)
            continue

