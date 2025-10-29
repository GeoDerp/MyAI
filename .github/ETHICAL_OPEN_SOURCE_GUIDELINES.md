# Ethical Open Source Guidelines for MyAI (RamaLama, UV, Containerized)

This document summarizes practical, ethical, and open-source best practices tailored for the MyAI research agent project, which uses RamaLama (local LLM serving), UV/async frameworks, and containerized deployment (Docker/Podman). It is intended for contributors, maintainers, and operators.

## Principles

- Safety and responsibility: prioritize minimizing harm. Avoid producing or silently enabling high-risk outputs. Require explicit human review for medium/high-impact findings.
- Privacy by design: keep sensitive data local where possible. Default to local LLMs and opt-out remote services unless explicitly configured.
- Transparency and provenance: persist and expose sources for claims so outputs can be audited and traced back to the original evidence.
- Open-source ethics: follow permissive licensing practices aligned with the project's license, and clearly document acceptable and unacceptable use.
- Reproducibility & minimal surprise: tests and CI should reproduce pipeline behavior deterministically as far as possible; network calls should be mockable by tests.

## Governance and Code of Conduct

- Include a `CODE_OF_CONDUCT.md` in the repo (reference contributor covenant or similar) with clear reporting channels.
- Contributors must sign-off on changes that materially alter data collection, model use, or privacy behavior (PR checklist item).
- Maintainer review: any changes that broaden data collection, add new network integrations, or change default model behavior must be reviewed by at least two maintainers and documented in release notes.

## License and Acceptable Use

- Make intended license explicit in `LICENSE` (repo already has one). For downstream clarity, add an `ACCEPTABLE_USE.md` describing uses that are permitted and discouraged (e.g., no attempts to facilitate wrongdoing, no large-scale scraping of copyrighted paywalled content without permission).

## Privacy & Data Handling

- Default to local-only: unless env vars explicitly enable external services (e.g., `OPENAI_API_KEY`, `EXA_API_KEY`), the system must default to local-only operation (RamaLama or mocked LLMs). Partial LLM transcripts, provenance bundles, and intermediate artifacts should be written to `MYAI_PARTIAL_DIR` (default `/tmp`).
- Explicit consent for remote services: require clear configuration and documented warnings when enabling remote LLMs or third-party retrievals.
- PII handling: detect and redact obvious PII in stored artifacts and logs by default (emails, credit card numbers, SSNs) before persisting or sending to remote services.
- Data minimization: persist only what is necessary for provenance. Consider hashing or truncating large source texts and storing raw archives only if an operator enables archival.
- Configurable retention: provide configuration (env var) for how long artifacts are stored (default: 30 days) and an operator command to purge stored artifacts.

## Provenance, Auditability, and Reproducibility

- Persist raw evidence metadata before transformation: for each ResearchSource, save {id, title, url, snippet, fetch_timestamp, retrieval_method}.
- Bundle provenance: when generating a report, write a `provenance_bundle.json` next to the HTML output containing sources, edges, and query metadata. For local runs this file should be written to `MYAI_PARTIAL_DIR` and linked from the rendered HTML.
- Make provenance exportable and machine-readable for audits. Include tool versions, model identifier, prompt templates used, and environment variables relevant to the run (masked where needed).

## Model & Prompting Safety

- Default conservative prompts: provide a curated set of safe prompts and make prompt templates auditable in the repo.
- Rate-limited and timeboxed LLM calls: set conservative timeouts and retry policies so runaway queries don't exhaust resources.
- Human-in-the-loop gating: for high-confidence claims or claims with potential harm, require a manual approval flag before publishing.

## Secure Deployment (Containers and RamaLama)

- Run RamaLama behind a local reverse proxy and bind only to localhost by default. Document how to safely bind to a network if needed (explicit env var).
- Image provenance: prefer pinned image digests in Dockerfiles and Podman deployments. Document and verify upstream image sources.
- Minimal runtime privileges: use non-root containers where possible. Drop Linux capabilities that are not needed.
- Secrets handling: do not store secrets in repo or in images. Read secrets from environment or secret management (don't check-in `.env` with secrets).
- Health and readiness: provide `/healthz` and `/readyz` endpoints for orchestration and monitoring; ensure they expose only non-sensitive runtime status.

## Logging and Telemetry

- Avoid telemetry by default. If telemetry or crash reporting is added, make it opt-in and document exactly what is collected.
- Log sensitivity levels: do not log raw source texts or sensitive user queries to public logs. Save raw artifacts to operator-controlled storage only.
- Operational metrics: collect non-sensitive metrics (e.g., latency, error rates) for maintainers to diagnose issues.

## Testing and CI

- Mock all external network calls in unit tests. Provide fixtures for a mock RamaLama endpoint and mock retrieval services.
- Add deterministic test inputs for core logic (summarization, scoring, evidence selection). Add tests that verify provenance bundle contents.
- CI must run unit tests and static checks. If runnable integration tests exist (e.g., with a small local model), gate them under a separate matrix or manual workflow.

## Contributor Checklist (PR template items)

- [ ] Is there an updated changelog or release note if behavior changed?
- [ ] Does the change introduce new external network calls? If so, document them and add opt-out configuration.
- [ ] Does the change affect privacy/data retention? Update docs and add an operator-facing migration/cleanup step if needed.
- [ ] Are new configurations or env vars documented in `README.md` and `COPILOT_GUIDE.md`?
- [ ] Are tests added/updated and passing locally?
- [ ] Has at least one maintainer reviewed the change (2 reviewers for privacy or data changes)?

## Maintainer Checklist (merging PRs)

- Verify no secrets were added in code or tests.
- Confirm tests and CI pass and check for flaky tests that may mask issues.
- Ensure the PR includes documentation updates when adding features (examples, env vars, and operational notes).

## Operational Runbook (quick operator steps)

- Start RamaLama locally (default binds to localhost:8080). If you must bind externally, only do so behind a secure network and change `RAMALAMA_ALLOW_EXTERNAL` to `true` in env to make the operator aware.
- To run web UI locally:

```bash
# run in a virtualenv or container
python webui.py
# or: docker-compose up webui
```

- Where to find outputs: rendered HTML is written to `/tmp/research_report.html` by default. Provenance bundles are saved beside that file.
- To purge artifacts older than N days (operator only): provide or run the `scripts/purge_artifacts.sh` script (operator should implement to match their storage).

## Example Configuration (secure defaults)

```bash
# Defaults: local-only, conservative timeouts
export MYAI_RENDERED_OUTPUT=/tmp/research_report.html
export RAMALAMA_HOST=127.0.0.1
export RAMALAMA_PORT=8080
export RAMALAMA_BIND_EXTERNAL=false
export LLM_TIMEOUT=30
export LLM_RETRIES=2
export ARTIFACT_RETENTION_DAYS=30
```

## Education and Responsible Usage

- Provide CONTRIBUTING.md with pointers to safe prompt construction, PII handling, and reproducible testing.
- Create example notebooks or demos that show how to run safely with local LLMs and mocked network calls.

## Closing notes

These guidelines aim to reduce harm, improve trust, and make it easier for operators and contributors to run MyAI responsibly. Implementation of the recommendations should be incremental: start by enforcing conservative LLM defaults, adding provenance persistence, and expanding tests to ensure reproducible behavior.
