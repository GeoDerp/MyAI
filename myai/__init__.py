"""myai package init

Expose high-level symbols for the package.

Important: avoid importing submodules at package import time. Importing
submodules from ``__init__.py`` (e.g. ``from . import research_agent``)
registers those submodules in ``sys.modules`` before runpy executes a
module via ``-m`` which triggers the RuntimeWarning you saw. To avoid
that, we lazily import submodules on attribute access via ``__getattr__``.
"""

__all__ = [
    "research_agent",
    "ramalama_config",
    "mcp_integration",
    "research_agent_example",
    "simple_demo",
]

import importlib


def __getattr__(name: str):
    """Lazily import submodules as attributes (PEP 562).

    This keeps ``import myai`` cheap and avoids populating ``sys.modules``
    with submodules until they're actually accessed (e.g. ``myai.research_agent``).
    """
    if name in __all__:
        module = importlib.import_module(f"{__name__}.{name}")
        # Cache on the package module to avoid re-importing on subsequent access
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)
