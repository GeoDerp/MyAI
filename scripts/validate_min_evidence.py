#!/usr/bin/env python3
"""Validate that research_question always returns at least 3 evidence sources.

This script monkeypatches `create_agent` in the `myai._research_agent` module
to return a fake agent whose `run` method returns a FinalAnswer with no
evidence. The module's fallback logic should add at least 3 evidence items.

Exit codes:
  0 - validation passed (>=3 evidence)
  2 - validation failed (<3 evidence)
"""
import asyncio
import sys
import pathlib

# Ensure repo root is on sys.path so `import myai` works when running this
# script from the project folder or CI
repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

# Some repository checkouts include a local folder named `pydantic` which
# shadows the real package. To allow importing `myai._research_agent` in a
# minimal CI environment we inject tiny fake `pydantic` and `pydantic_ai`
# modules into sys.modules if real ones are not available.
import types
if 'pydantic' not in sys.modules:
    fake_pyd = types.ModuleType('pydantic')
    # Minimal BaseModel that stores kwargs as attributes
    class _BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    def _Field(*args, **kwargs):
        return None
    fake_pyd.BaseModel = _BaseModel
    fake_pyd.Field = _Field
    sys.modules['pydantic'] = fake_pyd

if 'pydantic_ai' not in sys.modules:
    fake_pa = types.ModuleType('pydantic_ai')
    # Minimal Agent and RunContext placeholders to satisfy imports
    class Agent:
        def __init__(self, *a, **k):
            self.model = a[0] if a else None
        def tool(self, fn=None):
            # used as decorator; return the function unchanged
            def _decorator(f):
                return f
            return _decorator if fn is None else fn
    class RunContext:
        pass
    class ModelHTTPError(Exception):
        pass
    fake_pa.Agent = Agent
    fake_pa.RunContext = RunContext
    fake_pa.exceptions = types.SimpleNamespace(ModelHTTPError=ModelHTTPError)
    sys.modules['pydantic_ai'] = fake_pa

import myai._research_agent as ra


class FakeResult:
    def __init__(self, final):
        self.output = final


class FakeAgent:
    def __init__(self):
        # provide a minimal model representation used by research_question
        self.model = types.SimpleNamespace(model_name="fake-model")

    async def run(self, prompt, deps=None):
        # Create a FinalAnswer with no evidence so fallback must add items
        final = ra.FinalAnswer(
            answer="Fake answer",
            confidence=1,
            evidence=[],
            reasoning="",
            certainty_level="low",
        )
        return FakeResult(final)


def _fake_create_agent(model: str = "openai:gpt-4o"):
    return FakeAgent()


async def _main():
    # Monkeypatch the module-level create_agent
    ra.create_agent = _fake_create_agent

    # Run research_question which should call our FakeAgent and then
    # trigger the fallback to add at least 3 evidence items
    res = await ra.research_question(
        "List opensource tools that cover every layer of DevSecOps",
        max_iterations=1,
        min_confidence=9,
        model="http://localhost:8080/v1",
        enable_summarization=False,
    )

    count = len(res.evidence or [])
    print(f"Evidence count: {count}")
    for i, s in enumerate(res.evidence or [], 1):
        print(f" {i}. {s.title} (confidence: {s.confidence})")

    if count >= 3:
        print("Validation passed: >= 3 evidence items present")
        return 0
    else:
        print("Validation FAILED: fewer than 3 evidence items present", file=sys.stderr)
        return 2


def main():
    code = asyncio.run(_main())
    sys.exit(code)


if __name__ == '__main__':
    main()
