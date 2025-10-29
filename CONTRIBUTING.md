# Contributing to MyAI

Thanks for wanting to contribute! This project welcomes contributions from the community. Below are the main guidelines to make your contribution fast and easy to review.

## Getting started

- Fork the repository and create a topic branch for your work.
- Run the test suite before making changes:

```bash
# create a virtualenv and install deps (or use the project's preferred tool)
pip install -r requirements.txt
pytest -q
```

- Make small, focused commits with descriptive messages. Squash related changes when appropriate.

## Tests and style

- All new features must include unit tests where applicable. Use pytest and the existing test patterns under `tests/`.
- Keep behavior deterministic in tests by mocking network calls and the LLM where possible.
- Follow existing code style. The project uses standard Python idioms — keep imports organized and avoid broad refactors in unrelated files.

## Pull requests

- Open a PR against the `new-tooling` branch (or the target branch stated in the issue).
- Describe the change in the PR body, include rationale, and list any follow-up work.
- Add tests and update docs where public behavior changed (APIs, env vars, output locations).

## Environment variables and provenance (developer notes)

- The project uses several environment variables to opt-in integrations and control artifact locations. See `README.md` and `COPILOT_GUIDE.md` for a full list.
- By default, when a provenance store (LangGraph) is not configured the agent writes a JSON provenance bundle into `MYAI_PARTIAL_DIR` (defaults to `/tmp`). Tests should set `MYAI_PARTIAL_DIR` to a temporary directory.

If you plan to implement or modify integrations (LangGraph, TORM, Exa), add unit tests that simulate missing or failing external services and ensure the agent falls back to deterministic behavior.

Thanks again — contributions keep the project healthy and trustworthy.
