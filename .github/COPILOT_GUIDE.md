# Copilot Guide — MyAI Research Agent

Purpose
-------
This document gives a short, practical overview of the MyAI Personal Research Agent repository so an assistant (Copilot) can act as an effective collaborator. It summarizes architecture, key entrypoints, how to run common workflows, and common troubleshooting checks.

High-level summary
------------------
- Project: Personal Research Agent — iteratively researches a user question using web search, academic papers, documentation, and an LLM to synthesize evidence-backed reports.
- Core technologies: Python, Pydantic AI (agent framework), Flask (web UI), RamaLama (local LLM serving by default), DuckDuckGo search, and standard test tooling (pytest).

Key files and roles
-------------------
- `research_agent.py` / `myai/_research_agent.py`: Core agent implementation. Defines the agent, tools (web_search, analyze_source, summarize, etc.), and the main research loop (`research_question`).
- `research_agent_example.py`: CLI wrapper and usage examples.
- `simple_demo.py`: Minimal demo runner.
- `webui.py`: Flask app providing a web UI (GET/POST) and saving rendered HTML to `MYAI_RENDERED_OUTPUT` (default `/tmp/research_report.html`).
- `ramalama_config.py`: Utilities and recommended models for running a local RamaLama server. The repository prefers RamaLama for privacy and cost control; remote providers are opt-in and must be explicitly configured.
- `mcp_integration.py`: Integration points for Model Context Protocol extensions.
- `templates/index.html`: Jinja2 HTML template used by the Flask app to render results.
- `GUIDE.md`, `ARCHITECTURE.md`, `PROJECT_SUMMARY.md`, `FILES.md`: Documentation and developer guides.

Running the project (dev)
------------------------
1. Install dependencies (virtualenv recommended):
   - `pip install -r requirements.txt` or use the `pyproject.toml` / `poetry`/`pip` flow used by the repo.
2. Quick demo (local LLM recommended — RamaLama):
   - `python simple_demo.py`  # ensure `RAMALAMA_HOST`/`RAMALAMA_PORT` point to a running RamaLama instance
3. Run the CLI example:
   - `python research_agent_example.py --question "What is X?" --max-iterations 10`
4. Start the web UI (default binds to port 8081):
   - `python webui.py`  (or run under gunicorn in production).

Behavioral notes
----------------
- The agent iteratively searches, scores sources, records 'thoughts', and stops when confidence >= target or max iterations reached.
- The project prefers RamaLama by default. If `--use-ramalama` is passed (or the web UI toggles it), the code will configure the LLM manager to use a RamaLama base URL. Remote LLM usage is opt-in.
- `webui.py` writes a rendered HTML copy of results to `/tmp/research_report.html` (or the path in `MYAI_RENDERED_OUTPUT` env) — useful for automation.

Common troubleshooting checklist (fast)
------------------------------------
1. Is the LLM reachable?
   - For RamaLama: confirm `RAMALAMA_HOST` and `RAMALAMA_PORT`, and `curl` the RamaLama health endpoint.
   - For OpenAI: ensure `OPENAI_API_KEY` present in env.
2. Are the retrieval tools working (DuckDuckGo)?
   - Run `python -c "from myai import research_agent; print('ok')"` and a small `web_search` test.
3. Long-running POSTs: the Flask UI saves a rendered page to `MYAI_RENDERED_OUTPUT` (default `/tmp/research_report.html`) after completion — poll that file when automating. The provenance bundle is written beside the HTML in `MYAI_PARTIAL_DIR` (default `/tmp`).
4. Logs:
   - Example: `webui.py` can be run standalone and logs to stdout/stderr; gunicorn may be used in production.

Where Copilot can help (examples)
--------------------------------
- Implement a new tool (e.g., Slack integration) in `mcp_integration.py` and add tests under `tests/`.
- Improve error handling around the LLM step: add retries and better timeouts in `myai/_llm_manager_impl.py`.
- Add tests for the `research_question` flow to cover edge cases (empty results, LLM timeout, partial data).

Contact points for automation
-----------------------------
- Saved rendered HTML: `/tmp/research_report.html` (controlled via `MYAI_RENDERED_OUTPUT`).
- Web UI endpoints: `/` (GET/POST), `/healthz`, `/readyz`.

Last known commit / branch
--------------------------
- Branch: `new-tooling`
- Last commit: `a976954 | GeoDerp | Add Flask web interface for research question submissi` (short)

Notes
-----
Keep outputs deterministic when possible (mock network calls in tests). When synthesizing reports from the assistant, rely on the saved HTML for final output retrieval.

Recommended integrations
------------------------
To improve source-tracking, multi-perspective questioning, and local-model reliability the project recommends (and is compatible with) the following open-source integrations:

- LangGraph — knowledge-graph storage for sources and provenance. Use LangGraph to persist ResearchSource nodes, link articles to queries, and perform graph queries when generating cross-source evidence.
- TORM (Multi-Perspective Question Asking) — use TORM to expand the agent's question into multiple perspectives or subquestions. This improves coverage and reduces bias by prompting the agent to explicitly check alternate viewpoints.
- litellm with RamaLama — run a lightweight local LLM (litellm) behind RamaLama for on-prem inference. The project already supports RamaLama via `ramalama_config.py`; prefer local litellm models for privacy and cost control when available.
- Exa API — a lightweight external aggregation/search API for large-corpus retrieval. Use Exa to supplement DuckDuckGo and academic scrapers when higher recall is required.

All of these integrations follow the project's theme: prefer open-source, auditable components and explicit provenance. See `myai/integrations.py` for adapter stubs and recommended environment variables (e.g., `LANGGRAPH_URL`, `TORM_URL`, `RAMALAMA_HOST`/`RAMALAMA_PORT`, `EXA_API_KEY`).

Practical integration setup
---------------------------
Below are pragmatic, copy-pasteable steps and small code snippets to get each integration wired safely and in a way that supports provenance and high-confidence outputs.

1) LangGraph (provenance store)
   - Purpose: persist ResearchSource nodes, link them to queries, and query the provenance graph when generating cross-source evidence.
   - Env: set `LANGGRAPH_URL` to your LangGraph endpoint.
   - Minimal usage (pseudocode):

```py
from myai.integrations import langgraph_client
client = langgraph_client()
# client is a light adapter; implement real client calls to create nodes/edges
client['create_source'](title='Paper X', url='https://...')
```

2) TORM (multi-perspective question expansion)
   - Purpose: expand a user's question into diverse sub-questions to reduce bias and improve coverage.
   - Env: set `TORM_URL` to a running TORM service if available; otherwise the fallback in `myai.integrations.torm_expand_question` returns deterministic perspectives.
   - Example flow:

```py
from myai.integrations import torm_expand_question
perspectives = torm_expand_question('Is Y safe?')['perspectives']
for p in perspectives:
    result = research_question(p, max_iterations=6)
    # persist or aggregate results
```

3) litellm (via RamaLama) — local LLM for privacy and cost control
   - Purpose: provide on-prem LLM inference via RamaLama. Use litellm or another compatible model behind RamaLama.
   - Env: `RAMALAMA_HOST`, `RAMALAMA_PORT` (default host localhost, port 8080).
   - How to point the app at RamaLama (web UI or programmatic): pass `base_url=ramalama_model_url()` to `test_research_endpoint` or use the `use_ramalama` form checkbox in the UI.

4) Exa API (large-corpus retrieval)
   - Purpose: supplement DuckDuckGo and academic scrapers with an aggregation/search API when you need higher recall.
   - Env: `EXA_API_KEY` if required by the provider.
   - Example stub already present in `myai/integrations.py`: replace with real HTTP client to call Exa and normalise results into the `ResearchSource` format.

Provenance and high-confidence practices
---------------------------------------
To keep results trustworthy, follow these guardrails when integrating the above tools:

- Persist raw evidence: store original article metadata (title, url, snippet, fetched_at) in LangGraph or another durable store before any summarization/truncation.
- Link artifacts to the exact query/perspective that produced them (graph edges) so you can trace back any assertion to original sources.
- Multi-perspective validation: for each top-level claim, require evidence from at least two independent sources (configurable). Flag claims with single-source evidence for human review.
- LLM safe defaults: set conservative timeouts and retries for synth steps; capture partial outputs and save intermediate artifacts for post-hoc analysis.
- Human-in-the-loop: for medium/high-impact findings require a quick human validation step before publishing.

Evaluation & CI recommendations
-------------------------------
- Unit tests: mock LangGraph/TORM/RamaLama/Exa and assert the agent falls back cleanly to deterministic behaviors.
- Integration tests: run small end-to-end tests with a tiny corpus and a small local model (litellm) to verify the pipeline.
- Metrics: track precision@k of cited sources, rate of LLM hallucinations (manually labelled samples), and time-to-complete per research run.

Where to start (priority)
-------------------------
1. Wire LangGraph persistence for `ResearchSource` objects. This drastically improves traceability.
2. Use TORM to generate multiple perspectives per question and aggregate results.
3. Configure RamaLama to serve a litellm model locally and validate the LLM stage with small tests.
4. Add an optional Exa-backed retrieval path for high-recall runs.
