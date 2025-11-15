"""Ethical resource validation helpers."""
from __future__ import annotations

import logging
import os
from urllib.parse import urlparse
from typing import Dict, Tuple, List

logger = logging.getLogger("myai.ethics")
if not logger.handlers:
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(os.environ.get("MYAI_LOG_LEVEL", "INFO"))

DEFAULT_ALLOWED_HOSTS = {
    "duckduckgo.com",
    "html.duckduckgo.com",
    "api.crossref.org",
    "crossref.org",
    "export.arxiv.org",
    "arxiv.org",
    "api.exa.ai",
    "api.exa.example",
    "exa.ai",
    "llamacloud.com",
    "api.llamaindex.ai",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
}
INTERNAL_HOST_TOKENS = {"localhost", "127.0.0.1", "0.0.0.0"}


def _parse_host(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        return parsed.hostname.lower() if parsed.hostname else None
    # Strip credentials/ports if present
    host = value.split("@")[ -1 ]
    host = host.split(":")[0]
    host = host.strip("/ ")
    return host.lower() if host else None


def _gather_resource_hosts() -> Dict[str, str | None]:
    return {
        "LITELLM_BASE_URL": _parse_host(os.environ.get("LITELLM_BASE_URL")),
        "EXA_URL": _parse_host(os.environ.get("EXA_URL")),
        "LANGGRAPH_URL": _parse_host(os.environ.get("LANGGRAPH_URL")),
        "RAMALAMA_HOST": _parse_host(os.environ.get("RAMALAMA_HOST")),
        "TORM_URL": _parse_host(os.environ.get("TORM_URL")),
    }


def _allowed_hosts() -> set[str]:
    extra = os.environ.get("MYAI_ALLOWED_RESOURCE_HOSTS", "")
    extras = {h.strip().lower() for h in extra.split(",") if h.strip()}
    return DEFAULT_ALLOWED_HOSTS.union(extras)


def validate_resource_sources() -> Tuple[bool, List[str]]:
    """Ensure configured endpoints resolve to approved hosts."""
    hosts = _gather_resource_hosts()
    allowed = _allowed_hosts()
    issues: List[str] = []
    for name, host in hosts.items():
        if not host:
            continue
        if host in allowed or host in INTERNAL_HOST_TOKENS:
            continue
        if "." not in host:
            # treat custom container names as internal-only
            continue
        issues.append(f"{name} points to disallowed host '{host}'")
    return (len(issues) == 0, issues)


def assert_resource_policy_or_raise() -> None:
    ok, issues = validate_resource_sources()
    if ok:
        logger.info("Ethical resource validation passed")
        return
    message = (
        "Configured resource endpoints violate the ethical host allowlist: "
        + "; ".join(issues)
    )
    logger.error(message)
    raise RuntimeError(message)


def describe_resource_hosts() -> Dict[str, str | None]:
    """Return current resource host mapping for observability."""
    return _gather_resource_hosts()

__all__ = [
    "assert_resource_policy_or_raise",
    "validate_resource_sources",
    "describe_resource_hosts",
]


if __name__ == "__main__":
    ok, issues = validate_resource_sources()
    mapping = describe_resource_hosts()
    print("Configured resource hosts:")
    for name, host in mapping.items():
        print(f"  {name}: {host or '-'}")
    if ok:
        print("\n✅ Resource validation passed.")
    else:
        print("\n❌ Resource validation failed:")
        for issue in issues:
            print(f"  - {issue}")
        raise SystemExit(1)
