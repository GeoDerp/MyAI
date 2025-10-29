"""
Backwards-compatible shim for `research_agent` module expected by tests.
Re-exports the public symbols from the `myai.research_agent` package module.
"""
from myai.research_agent import *  # noqa: F401,F403

__all__ = getattr(__import__("myai.research_agent", fromlist=["*"]), "__all__", [])

# Provide a convenience module-level `research_agent` instance for tests that
# expect to import it directly. Create lazily in a safe manner so import-time
# failures do not happen when network credentials are absent.
try:
	from myai._research_agent import create_agent
	try:
		research_agent = create_agent()
		__all__.append("research_agent")
	except Exception:
		# If agent creation fails at import time (e.g., missing keys), expose a
		# None placeholder so tests can still import the symbol and choose to
		# mock it.
		research_agent = None
		__all__.append("research_agent")
except Exception:
	research_agent = None
	# keep __all__ unchanged if import fails
