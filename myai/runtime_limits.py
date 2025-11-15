"""Runtime budget utilities shared by agents and services."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional


DEFAULT_RUNTIME_LIMIT = 1800  # 30 minutes


def _coerce_positive_int(value: Optional[str | int | float], fallback: int) -> int:
    try:
        if value is None:
            raise ValueError
        as_int = int(float(value))
        return max(1, as_int)
    except Exception:
        return fallback


def resolve_runtime_limit_seconds(explicit: Optional[int | float | str] = None) -> int:
    """Return the effective runtime limit in seconds.

    Order of precedence:
      1. explicit argument (if provided)
      2. environment variable MYAI_MAX_RUNTIME_SECONDS
      3. DEFAULT_RUNTIME_LIMIT (30 minutes)
    """
    if explicit is not None:
        return _coerce_positive_int(explicit, DEFAULT_RUNTIME_LIMIT)
    env_val = os.environ.get("MYAI_MAX_RUNTIME_SECONDS")
    if env_val:
        return _coerce_positive_int(env_val, DEFAULT_RUNTIME_LIMIT)
    return DEFAULT_RUNTIME_LIMIT


@dataclass
class RuntimeLimitExceeded(RuntimeError):
    """Raised when a runtime budget is exceeded."""

    max_seconds: int
    elapsed: float
    step: Optional[str] = None
    state_snapshot: Optional[object] = None

    def __post_init__(self):
        msg = (
            f"Runtime budget exceeded after {self.elapsed:.2f}s; "
            f"limit {self.max_seconds}s"
        )
        if self.step:
            msg += f" during step '{self.step}'"
        RuntimeError.__init__(self, msg)


class RuntimeGuard:
    """Simple wall-clock runtime guard."""

    def __init__(self, max_seconds: Optional[int | float | str] = None):
        self.max_seconds = resolve_runtime_limit_seconds(max_seconds)
        self._started_at = time.monotonic()

    @property
    def started_at(self) -> float:
        return self._started_at

    def elapsed(self) -> float:
        return time.monotonic() - self._started_at

    def remaining(self) -> float:
        return max(0.0, self.max_seconds - self.elapsed())

    def ensure_within_budget(self, step: Optional[str] = None) -> None:
        elapsed = self.elapsed()
        if elapsed > self.max_seconds:
            raise RuntimeLimitExceeded(
                max_seconds=self.max_seconds,
                elapsed=elapsed,
                step=step,
            )