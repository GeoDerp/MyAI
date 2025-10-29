# Copilot Instructions — How to assist in MyAI

Quick purpose
-------------
This file tells the assistant exactly how to behave when asked to work on this repository. It contains step-by-step workflows, API-like contracts for common tasks, and prompt templates for interacting with the code and running the system.

High-level behavior
-------------------
- Always read the user's request fully. Break tasks into small, testable steps and write a todo entry before working (the repo's tooling expects a TODO list).
- Prefer executing small commands and reading files to gather context before editing code.
- When making code edits, use minimal changes and run quick sanity checks (lint/tests) where feasible.

Important constraints
---------------------
- Do not leak secrets found in the repo or environment.
- When running long background processes, prefer writing outputs to `MYAI_PARTIAL_DIR` (default `/tmp`) and poll for completion rather than blocking the client.

Common tasks & how to perform them
----------------------------------
1) Run a long research job via web UI and capture HTML
   - POST to `http://127.0.0.1:8081/` with the form fields from `templates/index.html`.
   - Poll `MYAI_RENDERED_OUTPUT` (or `MYAI_RENDERED_OUTPUT`) every 5–10s for up to user-specified timeout. Intermediate artifacts are placed in `MYAI_PARTIAL_DIR` (default `/tmp`).
   - If the HTML indicates "LLM did not return a response", capture the articles and return the partial findings; then recommend diagnosing LLM.

2) Diagnose LLM failures
   - Check `webui` logs (e.g., `/tmp/webui.log` if present) and gunicorn stdout.
   - Test `myai.api.test_research_endpoint` locally with a small input to capture exceptions.

3) Add a new tool
   - Implement new `@agent.tool` in `myai/_research_agent.py` following the existing pattern.
   - Add unit tests under `tests/` for the tool.

Prompt templates (for generating code/comments)
---------------------------------------------
- "Implement a new tool X that calls Y API, returns Z, and uses Pydantic models A for input and B for output. Include unit tests that mock network calls and verify behavior for success and failure." 

Detailed mini-contracts (examples)
----------------------------------
- research_run(input: {question:str, max_iterations:int, min_confidence:int}, output: {path: str})
  - Success: `/tmp/research_report.html` is written and contains `Research Results`.
  - Failure modes: LLM timeout, no articles found. Provide clear error messages and mitigation steps.

Edge cases to handle
--------------------
- Empty question: return validation error.
- No sources found: return a short 'no evidence' report and recommend enlarging the search query.
- LLM timeout: capture partial results and signal for re-run with smaller corpus or alternate model.

Testing and quality gates
-------------------------
- Run unit tests with `pytest -q` after changes; include small fast tests for new behavior.
- If adding runtime changes, run a quick smoke `python -m webui` and POST a small request to confirm the server returns HTML.

When finished
-------------
- Summarize what changed, which files were edited, and how you verified the change (tests run, outputs created). Add the summary to the PR description.

Contact points
--------------
- Main entrypoints: `research_agent.py`, `research_agent_example.py`, `webui.py`.
- Saved artifacts: `/tmp/research_report.html`, `/tmp/research_report_final.html`, `/tmp/research_summary.txt`.

Integration examples & env suggestions
------------------------------------
Use these environment variables to configure optional integrations:

```
LANGGRAPH_URL=http://localhost:7474
TORM_URL=http://localhost:9000
RAMALAMA_HOST=localhost
RAMALAMA_PORT=8080
EXA_API_KEY=your-exa-api-key
MYAI_RENDERED_OUTPUT=/tmp/research_report.html
```

Example: Expand question with TORM then run research using RamaLama model via `ramalama_model_url()`:

```
from myai.integrations import torm_expand_question, ramalama_model_url
from myai._research_agent import research_question

q = 'What is the current state of quantum computing?'
pers = torm_expand_question(q)['perspectives']
model_url = ramalama_model_url()
# pass model_url to LLM manager or web UI form (use_ramalama)
result = research_question(pers[0], base_url=model_url)
```

When diagnosing failures, first confirm these endpoints and env variables are reachable.

Concrete wiring steps (copy-paste)
----------------------------------
1) LangGraph
   - Start a LangGraph instance (docker/host) and set:

```
export LANGGRAPH_URL=http://localhost:7474
```

   - Minimal usage (replace stub with real client):

```py
from myai.integrations import langgraph_client
client = langgraph_client()
# implement client.create_node, client.create_edge, etc.
client.create_source({'title': 'Paper X', 'url': 'https://...'})
```

2) TORM (multi-perspective)
   - Start TORM and set:

```
export TORM_URL=http://localhost:9000
```

   - Use it to expand questions and iterate research across perspectives.

3) RamaLama + litellm (recommended local LLM)
   - Run RamaLama (container or local) hosting a litellm model. Example env:

```
export RAMALAMA_HOST=localhost
export RAMALAMA_PORT=8080
```

   - In the web UI enable "Use RamaLama" and set the model name (e.g., `litellm-small`). Programmatically pass `base_url=ramalama_model_url()` to the research call. RamaLama is the default LLM; remote providers must be enabled explicitly.

4) Exa API
   - Add `EXA_API_KEY` environment variable and implement the HTTP client in `myai/integrations.py` to return normalized search results.

Provenance patterns (must-have)
--------------------------------
- Before summarization, persist evidence node with these fields: id, title, url, text_snippet, fetch_timestamp, retrieval_method.
- When generating the final answer, include for each claim the provenance edges (source ids) and a confidence score.
- Emit a machine-readable provenance bundle (`.json`) alongside the HTML report for automated auditing.

High-confidence output guidelines for the assistant
--------------------------------------------------
- Always prefer multi-source corroboration: require at least 2 independent sources for strong claims.
- If answers rely on a single source, mark the claim as "single-source" and set confidence lower.
- Capture and expose intermediate artifacts (raw text snippets, extracted facts) so reviewers can verify.

Minimal test matrix
-------------------
- Unit: mock each integration and assert fallbacks.
- Smoke: run full pipeline with `litellm-small` (RamaLama) and assert `/tmp/research_report.html` contains `Research Results`.
- Regression: a nightly job that runs a short research on a stable question and checks for regressions in article counts and LLM behavior.
