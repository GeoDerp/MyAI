# Engineering Details — MyAI Research Agent

This document expands the `PROJECT_COMPLETION_CHECKLIST.md` into specific engineering details for each prioritized item. It lists target files, proposed function signatures, data shapes, tests to add, edge cases, quality gate checks, and PR guidance.

Note: this repository is intentionally small and is designed to run with a local LLM via RamaLama by default. All LLM-related code, tests, and examples should prefer the local RamaLama base URL (from `RAMALAMA_HOST`/`RAMALAMA_PORT`) unless a remote provider is explicitly enabled via environment variables.

Table of contents

- P0: LLM reliability and test harness
- P1: LangGraph provenance persistence
- P1: TORM question expansion and orchestration
- P1/P2: Exa retrieval adapter
- P2: Tests, CI, and smoke tests
- P2: Web UI improvements
- P3: Security hardening & container best practices
- Common data models and utilities

---

## P0: LLM reliability and test harness

Goal: provide a centralized, robust LLM calling interface with timeouts, retries, partial capture, and clear error types. The implementation should default to a RamaLama-compatible HTTP client and accept a `base_url` parameter so callers (including the web UI) can point at a running RamaLama server.

Files to create/update
- Add: `myai/_llm_manager_impl.py` (impl of retry wrapper and low-level HTTP client for RamaLama + optional remote adapters)
- Update: `myai/llm_manager.py` (public API, thin wrapper exposing RamaLama helpers)
- Update: `myai/_research_agent.py` (use new API for all LLM calls; accept a `base_url` for RamaLama)
- Add tests: `tests/test_llm_retries.py`

Function signatures and contracts

- class LLMError(Exception):
  - attributes: code: str, message: str, partial: Optional[str]

- def call_llm_with_retries(
    prompt: str,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 30,
    retries: int = 2,
    backoff_factor: float = 0.5,
    stream: bool = False,
) -> str

- def call_llm_once(prompt, base_url, model, timeout, stream) -> (status_code, response_text)

Data shapes
- Input: prompt (str) or dict with role/content for structured prompts.
- Output: response string or LLMError raised.

Edge cases
- 4xx responses: treat as fatal, no retry.
- 5xx or connection errors: retry `retries` times with exponential backoff.
- Streaming partial then error: persist partial to `/tmp/partial_llm_<ts>.txt` and raise LLMError(partial=...)
- Large prompt exceeding model or server payload limits: detect 413 or similar and raise specific error.

Tests to add
- `test_llm_retries.py`:
  - Happy path: single successful call returns text.
  - Transient 5xx then success: ensure retry occurs and success returned.
  - Persistent 5xx: ensure retries are attempted then LLMError raised.
  - 4xx error: ensure immediate LLMError without retries.
  - Simulate streaming partial: partial saved, LLMError with partial.

Quality gates
- Unit tests: PASS
- Lint/typecheck: PASS

Migration notes
- Call sites in `myai/_research_agent.py` may expect direct LLM responses; update to use exceptions and partial handling.

---

## P1: LangGraph provenance persistence

Goal: ensure all retrieved sources are recorded in a provenance store (LangGraph) or saved locally as a fallback.

Files to create/update
- Update/Add: `myai/integrations.py` — add `langgraph_client()`, `LangGraphClient` class
- Update: `myai/_research_agent.py` — hook to call `create_source` before summarization
- Add: `myai/provenance.py` (helpers for bundle writing and id generation)
- Add tests: `tests/test_integrations_langgraph.py`

Function signatures

- class LangGraphClient:
  - def __init__(self, base_url: str)
  - def create_source(self, source: dict) -> str  # returns source_id
  - def create_claim(self, claim: dict, source_ids: List[str]) -> str
  - def bulk_create_sources(self, sources: List[dict]) -> List[str]

- def langgraph_client() -> LangGraphClient  # reads env LANGGRAPH_URL; returns client or None

Data shapes
- ResearchSource: {
  id: str (uuid),
  title: str,
  url: Optional[str],
  snippet: str,
  fetch_timestamp: str (ISO8601),
  retrieval_method: str,
}

Edge cases
- LangGraph unreachable: write `provenance_bundle_<ts>.json` into `/tmp` and log a warning.
- Idempotency: if the same URL is re-ingested, ensure we either return existing ID or create deduped node using a deterministic id (hash of url+title)

Tests to add
- `test_integrations_langgraph.py`:
  - Verify client POSTs expected payload when LANGGRAPH_URL is set (mock server)
  - Verify fallback file is written when LANGGRAPH_URL unset or unreachable

Quality gates
- Unit tests: PASS
- Verify produced `provenance_bundle.json` contains required fields

Migration notes
- Ensure sources get a new `source_id` field stored in ResearchSource objects used by the pipeline.

---

## P1: TORM question expansion and orchestration

Goal: expand user questions into perspectives and run the research pipeline for each.

Files to create/update
- Update/Add: `myai/integrations.py` — `torm_expand_question(question: str) -> dict`
- Add: `myai/aggregator.py` — orchestrate per-perspective runs, dedupe sources, and aggregate claims
- Update: `research_agent_example.py` or add `scripts/run_multi_perspective.py`
- Add tests: `tests/test_torm_integration.py`, `tests/test_aggregator.py`

Function signatures
- def torm_expand_question(question: str, base_url: Optional[str] = None) -> dict
  - returns: { 'perspectives': [ { 'id': str, 'text': str } ] }

- def aggregate_perspective_results(results: List[ResearchResult], min_sources_for_high_confidence: int = 2) -> AggregatedResult

Edge cases
- TORM unreachable: fallback to deterministic perspectives list (e.g., ["core question", "narrow technical", "policy/ethics"]) as string list
- Perspectives with large overlap: dedupe by normalized text (lower/strip punctuation)

Tests to add
- TORM fallback behavior
- Aggregation merging overlapping claims

Quality gates
- Unit tests for aggregator

---

## P1/P2: Exa retrieval adapter

Goal: add a pluggable high-recall retrieval adapter for better recall.

Files to create/update
- Update/Add: `myai/integrations.py` — `exa_search(query: str, api_key: Optional[str]) -> List[dict]`
- Update: retrieval pipeline (in `myai/academic_retrieval.py` or `_research_agent.py`) to call Exa when configured
- Add tests: `tests/test_exa_adapter.py`

Function signatures
- def exa_search(query: str, api_key: Optional[str]) -> List[ResearchSource]

Edge cases
- Rate limiting / quota exceeded: detect and fallback to other retrievals
- Dedupe results across retrieval backends

Tests
- Mock Exa response, validate normalization and dedupe

---

## P2: Tests, CI, and smoke tests

Goal: make the repo testable and add CI to run tests on PRs.

Files to create/update
- Add: `tests/conftest.py` — provide fixtures: `mock_llm_server`, `mock_retrieval_server`
- Add unit tests described above
- Add CI workflow: `.github/workflows/python-ci.yml`

CI steps
- Setup python
- Install deps from `pyproject.toml`
- Run `pytest -q`
- (Optional) Upload coverage results

Edge cases
- Tests that rely on network must be mocked

---

## P2: Web UI improvements

Goal: improve `webui.py` observability and ensure outputs and provenance are written atomically.

Files to update
- `webui.py`:
  - Accept `base_url` or `use_ramalama` param and pass `base_url` into research flow
  - Write HTML atomically: write to `MYAI_RENDERED_OUTPUT.tmp` then rename
  - Write `provenance_bundle.json` beside HTML
  - Log to `/tmp/webui.log` when debug enabled

- `templates/index.html`:
  - Ensure form has fields: question, max_iterations, use_ramalama checkbox, model

Tests to add
- `tests/test_webui.py` using Flask test client and mocked LLM

---

## P3: Security hardening & container best practices

- Update `Dockerfile` and `Dockerfile.webui` to use pinned image digests where possible and a non-root runtime user.
- Add `SECURITY.md` and expand `README.md` with secure deployment recipes.
- Ensure `ramalama_config.py` documents local-only binding and safe defaults.

---

## Common data models and utilities

- Standardize `ResearchSource` pydantic model (if not already) in `myai/models.py` or similar. Required fields:
  - id: str
  - title: str
  - url: Optional[str]
  - snippet: str
  - fetched_at: str
  - retrieval_method: str
  - source_id (optional): str   # LangGraph persisted id

- Standardize `ResearchResult` / `AggregatedResult` models for orchestration.

---

## PR checklist for maintainers

- Ensure tests pass and no secrets are included.
- Verify changelog and docs updated for behavior changes.
- Validate provenance bundle format and that new env vars are documented.

---

If you'd like, I will begin implementing a concrete item now. I recommend starting with P0 (LLM retry wrapper and tests) and then P1(langgraph adapter + local fallback). Which should I start on now? If yes, I'll update the todo list, create the files, and run tests.
