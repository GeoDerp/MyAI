# Project Completion Checklist — MyAI Research Agent

This document lists required changes, priorities, file targets, tests, environment variables, acceptance criteria, and rough effort estimates for the MyAI research agent. The project is intentionally small and designed to prefer a local RamaLama LLM by default and file-based provenance in `/tmp` unless configured otherwise.

Summary of high-level goals

- Add multi-perspective question expansion (TORM) support and an orchestration layer to aggregate results.
- Add a pluggable high-recall retrieval adapter (Exa) and normalize retrieval results.
- Harden web UI and automation endpoints; make outputs reproducible and saved to `/tmp` by default.
- Improve tests and CI to ensure reliability and reproducibility.
- Operational and security hardening for containerized deployments (RamaLama, Podman/Docker).

Prioritized checklist

P0 — LLM reliability and test harness (High priority)

- What
  - Implement a retry + timeout wrapper for all LLM calls.
  - Add partial-output capture and persist partials to `/tmp`.
  - Add unit tests mocking network failures.

- Files to change / add
  - Add: `myai/_llm_manager_impl.py` (new) — contains `call_llm_with_retries` and `LLMError`.
  - Update: `myai/llm_manager.py` — expose wrapper APIs.
  - Update: `myai/_research_agent.py` — use wrapper for all LLM calls.
  - Add tests: `tests/test_llm_retries.py`.

- Env vars
- `LLM_TIMEOUT` (default 30)
- `LLM_RETRIES` (default 2)
- `RAMALAMA_HOST` / `RAMALAMA_PORT` (defaults: localhost / 8080)

- Acceptance criteria
- Unit tests validate retry behavior (succeeds on transient 5xx, raises on persistent 5xx, does not retry 4xx).
- Research flows log and persist partial outputs when LLM fails. Partial outputs are saved to `MYAI_PARTIAL_DIR` (default `/tmp`).

- Estimate: 4–8 hours

---

P1 — Provenance persistence and LangGraph adapter (High priority)

- What
- Persist every retrieved ResearchSource to a provenance store before summarization. Default behavior for local/small deployments is to write a file-based provenance bundle to `MYAI_PARTIAL_DIR` (default `/tmp`).
- Implement a `LangGraph` adapter with an opt-in configuration via `LANGGRAPH_URL`. When unset or unreachable, fall back to the file bundle.
- Emit `provenance_bundle.json` alongside the HTML report.

- Files to change / add
  - Update/Add: `myai/integrations.py` — implement `langgraph_client()`, `exa_search()`, `torm_expand_question()` stubs.
  - Update: `myai/_research_agent.py` — call `langgraph_client().create_source(...)` before summarization; store source ids in the ResearchSource objects.
  - Add: persistence fallback: `myai/provenance.py` (optional) or write directly to `/tmp/provenance_bundle_<ts>.json`.
  - Add tests: `tests/test_integrations_langgraph.py`.

- Env vars
- `LANGGRAPH_URL` (optional)
- `MYAI_RENDERED_OUTPUT` (existing; default `/tmp/research_report.html`)
- `MYAI_PARTIAL_DIR` (default `/tmp`) — where partial LLM outputs and provenance bundles are written.

- Acceptance criteria
- When `LANGGRAPH_URL` is set, the adapter attempts to POST source nodes and returns stable ids.
- When `LANGGRAPH_URL` is not set or unreachable, a `provenance_bundle.json` is created in `MYAI_PARTIAL_DIR` and `research_report.html` references it.

- Estimate: 8–16 hours

---

P1 — TORM question expansion and multi-perspective orchestration (High priority)

- What
  - Add TORM integration to expand questions into perspectives, run research per perspective, and aggregate results.

- Files to change / add
  - Update/Add: `myai/integrations.py` — `torm_expand_question(question: str) -> dict`.
  - Add: `myai/aggregator.py` (new) — orchestrator that runs research per perspective and aggregates results, dedupes evidence, and normalizes claims.
  - Update: `research_agent_example.py` or add `scripts/run_multi_perspective.py` to demonstrate.
  - Add tests: `tests/test_torm_integration.py`, `tests/test_aggregator.py`.

- Env vars
  - `TORM_URL` (optional)

- Acceptance criteria
  - With `TORM_URL` set, the system requests perspectives from TORM and runs research for each.
  - Without `TORM_URL`, a deterministic fallback list of perspectives is used.

- Estimate: 4–8 hours

---

P1/P2 — Exa retrieval adapter (Medium priority)

- What
  - Add Exa adapter as an optional high-recall retrieval backend and normalize results into ResearchSource objects.

- Files to change / add
  - `myai/integrations.py`: implement `exa_search(query, api_key)` and normalization.
  - `myai/academic_retrieval.py` or `myai/_research_agent.py`: wire Exa into retrieval pipeline.
  - Add tests: `tests/test_exa_adapter.py`.

- Env vars
  - `EXA_API_KEY` (optional)

- Acceptance criteria
  - When `EXA_API_KEY` present, Exa is used alongside DuckDuckGo results; results are normalized and deduplicated.

- Estimate: 6–12 hours

---

P2 — Tests, CI, and reproducible smoke tests (Medium priority)

- What
  - Expand unit tests, add fixtures for mocking RamaLama and retrieval services.
  - Add GitHub Actions workflow to run unit tests and a gated smoke test.

- Files to change / add
  - Add: `tests/conftest.py` with fixtures for mock LLM and mock HTTP services.
  - Add: `tests/test_integration_smoke.py` (gated) — runs `simple_demo.py` or `research_agent_example.py` with a small local model or fully mocked LLM.
  - Add CI workflow: `.github/workflows/python-ci.yml`.

- Acceptance criteria
  - `pytest -q` passes locally in a dev environment with mocked services.
  - CI runs unit tests on PRs; smoke test runs in a separate workflow or on main.

- Estimate: 8–16 hours

---

P2 — Web UI improvements and observability

- What
  - Ensure `webui.py` supports base_url overrides, writes HTML atomically, and writes `provenance_bundle.json` beside the HTML. Add log file output to `/tmp/webui.log`.

- Files to change / add
  - Update: `webui.py` — accept `base_url` param, write outputs atomically; expose startup flags.
  - Update: `templates/index.html` — ensure form includes `use_ramalama` and model name fields; optionally add `debug` checkbox.
  - Tests: `tests/test_webui.py` running Flask test client with mocked LLM.

- Acceptance criteria
  - POST to the running web UI with `use_ramalama` and `model` returns a saved HTML report and a `provenance_bundle.json`.

- Estimate: 4–8 hours

---

P3 — Security hardening & container operationalization (Low/ongoing)

- What
  - Pin Docker/Podman image digests, use non-root containers, document secure RamaLama binding, and add guidance for secrets management.

- Files to change / add
  - Update: `Dockerfile`, `Dockerfile.webui` — pin image digests, non-root user steps.
  - Add: `SECURITY.md` with deployment recommendations.
  - Update: `docker-compose.yml` (if included) to document network isolation and secret sources.

- Acceptance criteria
  - Container images are pinned; default config binds RamaLama to 127.0.0.1.

- Estimate: 4–8 hours

---

P3 — Provenance-based claim auditing and aggregation (Longer term)

- What
  - Implement aggregator claim normalization, multi-source corroboration thresholds, and a claim-level review UI or CLI.

- Files to change / add
  - Add: `myai/claims.py` and expand `myai/aggregator.py`.
  - Add tests: `tests/test_claims.py`.

- Acceptance criteria
  - Claims must be associated with ≥2 independent sources for high-confidence labeling; otherwise flagged single-source.

- Estimate: 12–24 hours

---

Operational and documentation tasks (small, but important)

- Add or update these docs:
  - `CONTRIBUTING.md` — contributor workflow and PR checklist.
  - `CODE_OF_CONDUCT.md` — contributor covenant.
  - `ACCEPTABLE_USE.md` — license and acceptable use.
  - Update `README.md` and `COPILOT_GUIDE.md` with new env vars and quickstarts for running locally with RamaLama.
  - `ETHICAL_OPEN_SOURCE_GUIDELINES.md` — already added.

- Files touched: `README.md`, `COPILOT_GUIDE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `ACCEPTABLE_USE.md`.

- Estimate: 4–8 hours


Testing & Quality Gates

- Build: ensure `pip install -e .` or `poetry install` runs successfully. Validate `pyproject.toml` entries.
- Lint/Typecheck: run flake8/mypy where applicable.
- Tests: unit tests should pass; smoke tests optional/gated.
- If I implement code, I will run these checks and report PASS/FAIL.


Acceptance criteria for "project finished"

- All P0/P1 items implemented and covered by tests.
- Provenance is persisted to either LangGraph or local bundle and included in every report.
- Multi-perspective orchestration works with TORM or deterministic fallback and aggregates results.
- CI runs unit tests on PRs and optionally runs gated smoke tests.
- Secure container images and documented deployment guidance exist.


Suggested immediate next steps (what I can implement next)

1. Implement `call_llm_with_retries` and unit tests (P0). — immediate, low-risk.
2. Implement `myai/integrations.py` langgraph/torm/exa stubs + file-based provenance fallback (P1). — next recommended.
3. Add `tests/conftest.py` with mock LLM fixture and run `pytest -q`.

If you want, I will implement step 1 now. Tell me which item to implement and I will start working on it, update the todo list, make code changes, and run tests.
