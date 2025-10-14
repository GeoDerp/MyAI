"""
Original research_agent module moved into package as _research_agent
"""

"""
Personal Research Agent using Pydantic AI, RamaLama, and MCP tools
This agent researches questions using multiple sources and iterates until confident.
"""
import asyncio
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, Field
import os
import logging
from pydantic_ai import Agent, RunContext
import json

# Avoid importing potentially heavy/optional provider and tool modules at
# import time. We'll import them lazily when needed so the package can be
# imported even when OpenAI/duckduckgo or local RamaLama services aren't
# available.
_duckduckgo_tool = None

def _get_duckduckgo_tool():
    global _duckduckgo_tool
    if _duckduckgo_tool is None:
        # import lazily; if the optional dependency isn't installed we
        # provide a silent no-op stub so callers don't see noisy
        # import-time warnings or errors.
        try:
            # Some versions of the duckduckgo client emit a RuntimeWarning
            # about package renaming; filter it here so startup logs stay clean.
            import warnings
            with warnings.catch_warnings():
                # Use a safe regex message match and filter RuntimeWarning during import
                warnings.filterwarnings("ignore", category=RuntimeWarning, message=r".*duckduckgo_search.*renamed.*")
                from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool as _dd
            # Wrap the factory so the tool's function suppresses the runtime warning when invoked
            def _factory_wrapper(*f_args, **f_kwargs):
                tool = _dd(*f_args, **f_kwargs)
                try:
                    orig_func = tool.function
                except Exception:
                    return tool
                import warnings as _warnings

                class _FuncWrapper:
                    async def __call__(self, *a, **kw):
                        with _warnings.catch_warnings():
                            _warnings.filterwarnings("ignore", category=RuntimeWarning, message=r".*duckduckgo_search.*renamed.*")
                            return await orig_func(*a, **kw)

                tool.function = _FuncWrapper()
                return tool

            _duckduckgo_tool = _factory_wrapper
        except Exception:
            # Minimal stub with compatible shape used by the agent tools.
            class _StubTool:
                takes_ctx = False

                class function:
                    @staticmethod
                    async def __call__(*args, **kwargs):
                        # Return an empty / benign result so the agent simply
                        # falls back to other sources instead of failing.
                        return ""

            _duckduckgo_tool = lambda *_, **__: _StubTool()
    return _duckduckgo_tool
from . import cache as _cache
from typing import Dict, Any


def record_source_with_condensation(
    deps: "ResearchDependencies",
    title: str,
    content: str,
    url: Optional[str],
    confidence: int,
    enable_summarization: bool = False,
    summarization_threshold: int = 800,
    model_id: str = "local",
) -> "ResearchSource":
    """Helper that records a ResearchSource on deps, optionally condensing long content

    Returns the created ResearchSource instance.
    """
    fingerprint = None
    meta = None
    final_content = content
    if enable_summarization and isinstance(content, str) and len(content) > summarization_threshold:
        try:
            condensed = _cache.summarize_document_with_content(
                doi=url or "", condensation_config={}, max_tokens=summarization_threshold, model_id=model_id, prompt_fingerprint=None, source_text=content
            )
            fingerprint = condensed.get("fingerprint")
            meta = condensed.get("meta")
            final_content = condensed.get("summary")
        except Exception:
            pass

    source = ResearchSource(
        title=title,
        content=final_content,
        url=url,
        confidence=confidence,
        fingerprint=fingerprint,
        meta=meta,
    )
    deps.sources_collected.append(source)
    return source


# Logging
logger = logging.getLogger(__name__)


def should_enable_summarization(model: str | None, enable_summarization: Optional[bool]) -> tuple[bool, str]:
    """Decide whether summarization should be enabled.

    Returns (enabled: bool, reason: str).
    If enable_summarization is explicitly provided (True/False) that value
    is used and the reason notes an explicit override. Otherwise a small
    heuristic enables summarization for local RamaLama endpoints, when
    RAMALAMA env vars are present, or when common local model names are
    detected (e.g., 'granite', 'gpt-oss', 'deepseek').
    """
    if enable_summarization is not None:
        return bool(enable_summarization), "explicit override"

    ramalama_host = os.environ.get('RAMALAMA_HOST')
    ramalama_port = os.environ.get('RAMALAMA_PORT')
    model_str = model or ""
    is_local_endpoint = isinstance(model_str, str) and model_str.startswith(('http://', 'https://'))
    likely_local_model_name = any(k in model_str for k in ("granite", "gpt-oss", "deepseek"))

    enabled = bool(is_local_endpoint or ramalama_host or ramalama_port or likely_local_model_name)
    parts = []
    if is_local_endpoint:
        parts.append('local_endpoint')
    if ramalama_host or ramalama_port:
        parts.append('ramalama_env')
    if likely_local_model_name:
        parts.append('local_model_name')
    reason = 'heuristic:' + (','.join(parts) if parts else 'no_local_indicators')
    return enabled, reason



# ============================================================================
# Data Models
# ============================================================================


class ResearchSource(BaseModel):
    """A source of information found during research"""
    title: str = Field(description="Title or description of the source")
    content: str = Field(description="Key information from the source")
    url: Optional[str] = Field(None, description="URL if applicable")
    confidence: int = Field(description="Confidence level 0-10 in this source", ge=0, le=10)
    # Provenance fields populated when content is condensed/cached
    fingerprint: Optional[str] = Field(None, description="Fingerprint of cached summary if available")
    meta: Optional[dict] = Field(None, description="Additional provenance metadata")


class ResearchThought(BaseModel):
    """Agent's thinking process"""
    observation: str = Field(description="What the agent learned")
    analysis: str = Field(description="Analysis of the information")
    next_action: str = Field(description="What to investigate next")
    confidence: int = Field(description="Current confidence level 0-10", ge=0, le=10)


class FinalAnswer(BaseModel):
    """Final research answer with evidence"""
    answer: str = Field(description="The definitive answer to the question")
    confidence: int = Field(description="Final confidence level 0-10", ge=0, le=10)
    evidence: list[ResearchSource] = Field(description="Supporting evidence")
    reasoning: str = Field(description="Explanation of how the answer was reached")
    certainty_level: Literal["low", "medium", "high", "very_high"] = Field(
        description="Overall certainty in the answer"
    )
    # Map of fingerprint -> provenance metadata (title/url/confidence/summary_meta)
    provenance: Optional[dict] = Field(None, description="Mapping of summary fingerprints to provenance metadata")


@dataclass
class ResearchDependencies:
    """Dependencies for the research agent"""
    max_iterations: int = 10
    min_confidence: int = 8  # Minimum confidence to stop (0-10)
    iteration_count: int = 0
    sources_collected: Optional[list[ResearchSource]] = None
    thoughts: Optional[list[ResearchThought]] = None
    
    def __post_init__(self):
        if self.sources_collected is None:
            self.sources_collected = []
        if self.thoughts is None:
            self.thoughts = []

    # Opt-in summarization settings to reduce prompt size for local models
    enable_summarization: bool = False
    summarization_threshold: int = 800



# ============================================================================
# Research Agent with Looping Logic
# ============================================================================

def create_agent(model: str = "openai:gpt-4o") -> Agent:
    """Create and return a configured Agent instance for the requested model.

    Tools are registered inside this factory so importing this module does not
    attempt to initialize cloud providers (like OpenAI) at import time.
    """
    # If a full HTTP URL is provided (for example RamaLama's OpenAI-compatible
    # endpoint like http://ramalama:8080/v1) build an OpenAI provider that
    # points at that base URL and create an OpenAIChatModel instance. Use a
    # shorter instruction set for local models to avoid exceeding context
    # limits on smaller local models.
    # If RAMALAMA_HOST or RAMALAMA_PORT env vars are set and no explicit
    # model HTTP URL was provided, prefer building a RamaLama HTTP endpoint
    # and avoid initializing OpenAI cloud clients.
    ramalama_host = os.environ.get('RAMALAMA_HOST')
    ramalama_port = os.environ.get('RAMALAMA_PORT')
    if not (isinstance(model, str) and model.startswith(('http://', 'https://'))) and ramalama_host and ramalama_port:
        model = f"http://{ramalama_host}:{ramalama_port}/v1"

    if isinstance(model, str) and model.startswith(('http://', 'https://')):
        # RamaLama/OpenAI-compatible HTTP endpoint provided. Import the
        # OpenAI provider / model classes lazily so we avoid initializing
        # cloud clients at import time when a local RamaLama is used.
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        ram_model_name = os.environ.get('RAMALAMA_MODEL') or os.environ.get('RAMALAMA_MODEL_NAME') or 'granite'
        provider = OpenAIProvider(base_url=model)
        model_obj = OpenAIChatModel(ram_model_name, provider=provider)

        short_instructions = (
            "You are a concise research assistant.\n"
            "Gather reliable sources, cross-check facts, and produce a clear evidence-backed answer.\n"
            "After each search, record a short thought with confidence (0-10) and next action.\n"
            "Stop when confidence >= target or max iterations reached."
        )

        agent = Agent(
            model_obj,
            deps_type=ResearchDependencies,
            output_type=FinalAnswer,
            retries=2,
            instructions=short_instructions,
        )
    else:
        # Non-HTTP model string (e.g., provider:model). Let the Agent infer
        # the provider from the model string and use the default, more
        # verbose instructions suitable for larger-context models.
        verbose_instructions = (
            "You are a research assistant. Gather sources, cross-check facts, "
            "and produce an evidence-backed answer. After each step, record a "
            "thought with confidence (0-10) and next action. Stop when confidence >= target or max iterations reached."
        )

        agent = Agent(
            model,
            deps_type=ResearchDependencies,
            output_type=FinalAnswer,
            retries=2,
            instructions=verbose_instructions,
        )

    # Register tools on the agent
    @agent.tool
    async def web_search(ctx: RunContext[ResearchDependencies], query: str) -> str:
        print("🔍 Searching web:", query)
        # Limit results to keep outputs small for local models
        tool = _get_duckduckgo_tool()(max_results=3)
        func = tool.function
        if getattr(tool, 'takes_ctx', False):
            results = await func(ctx, query)
        else:
            results = await func(query)
        # If results are long, either summarize (if enabled) or truncate
        if isinstance(results, str) and len(results) > ctx.deps.summarization_threshold:
            if ctx.deps.enable_summarization:
                results = summarize_text(results, ctx.deps.summarization_threshold)
            else:
                results = results[: ctx.deps.summarization_threshold] + "... [truncated]"
        return f"Web search results for '{query}':\n{results}"

    @agent.tool
    async def analyze_source(
        ctx: RunContext[ResearchDependencies],
        title: str,
        content: str,
        url: Optional[str],
        confidence: int
    ) -> str:
        # Use helper to record and optionally condense the source
        source = record_source_with_condensation(
            deps=ctx.deps,
            title=title,
            content=content,
            url=url,
            confidence=confidence,
            enable_summarization=ctx.deps.enable_summarization,
            summarization_threshold=ctx.deps.summarization_threshold,
            model_id=os.environ.get('RAMALAMA_MODEL','local')
        )
        print("📚 Recorded source:", title, "(confidence:", confidence, "/10)")
        return f"Source recorded. Total sources: {len(ctx.deps.sources_collected)}"


    @agent.tool
    async def record_thought(
        ctx: RunContext[ResearchDependencies],
        observation: str,
        analysis: str,
        next_action: str,
        confidence: int
    ) -> str:
        thought = ResearchThought(
            observation=observation,
            analysis=analysis,
            next_action=next_action,
            confidence=confidence
        )
        # Each recorded thought represents one iteration. Increment here
        ctx.deps.iteration_count += 1
        ctx.deps.thoughts.append(thought)
        print("💭 Iteration", ctx.deps.iteration_count, ": Confidence", f"{confidence}/10")
        print("   Next:", next_action)
        should_stop = (
            confidence >= ctx.deps.min_confidence or 
            ctx.deps.iteration_count >= ctx.deps.max_iterations
        )
        if should_stop:
            status = "HIGH CONFIDENCE REACHED!" if confidence >= ctx.deps.min_confidence else "Max iterations reached"
            return f"Thought recorded. {status} Ready to provide final answer."
        return f"Thought recorded. Continue researching. (Iteration {ctx.deps.iteration_count}/{ctx.deps.max_iterations})"

    @agent.tool
    async def check_academic_papers(
        ctx: RunContext[ResearchDependencies],
        topic: str
    ) -> str:
        print("📄 Searching academic sources:", topic)

        def fallback(topic_inner: str):
            tool = _get_duckduckgo_tool()(max_results=3)
            func = tool.function
            # shim synchronous fallback for simplicity
            if getattr(tool, 'takes_ctx', False):
                # Note: this branch is unlikely in the duckduckgo tool; prefer the other
                import asyncio
                return asyncio.get_event_loop().run_until_complete(func(ctx, topic_inner))
            return asyncio.get_event_loop().run_until_complete(func(topic_inner))

        # Use CrossRef-first search with simple quality filtering. If insufficient,
        # fallback to duckduckgo search.
        try:
            # Import academic_retrieval lazily to avoid import-time network calls
            import myai.academic_retrieval as academic_retrieval
            candidates = academic_retrieval.search_with_fallback(
                topic,
                max_results=5,
                min_year=None,
                prefer_peer_review=True,
                prefer_oa=True,
                fallback_fn=lambda q: [
                    {"title": "Web fallback result", "DOI": None, "URL": None, "raw": {"text": fallback(q)}}
                ],
            )
        except Exception as e:
            # If academic retrieval or its import fails, fallback to a web search result.
            print("Academic retrieval unavailable, falling back to web search.")
            candidates = [{"title": "Fallback: web search", "DOI": None, "URL": None, "raw": {"text": str(e)}}]

        # Serialize candidates into a compact string for agent consumption
        out_lines = []
        for c in candidates:
            title = c.get("title") or c.get("raw", {}).get("title") or "(no title)"
            doi = c.get("DOI")
            url = c.get("URL")
            summary = c.get("raw", {}).get("text") if c.get("raw") else None
            # If summarization enabled and summary is long, create or fetch condensed summary
            fingerprint = None
            if ctx.deps.enable_summarization and isinstance(summary, str) and len(summary) > ctx.deps.summarization_threshold:
                # Use cache.summarize_document_with_content to condense and cache
                try:
                    condensed = _cache.summarize_document_with_content(
                        doi or "", {}, max_tokens=ctx.deps.summarization_threshold, model_id=os.environ.get('RAMALAMA_MODEL','local'), prompt_fingerprint=None, source_text=summary
                    )
                    fingerprint = condensed.get("fingerprint")
                    # replace summary with condensed summary text
                    summary = condensed.get("summary")
                    # attach meta to candidate for provenance
                    c.setdefault("meta", {})
                    c["meta"]["summary_fingerprint"] = fingerprint
                    c["meta"]["summary_meta"] = condensed.get("meta")
                except Exception:
                    pass
            line = f"- {title}"
            if doi:
                line += f" (DOI: {doi})"
            if url:
                line += f" {url}"
            if summary and isinstance(summary, str) and len(summary) > 200:
                if ctx.deps.enable_summarization:
                    summary = summarize_text(summary, ctx.deps.summarization_threshold)
                else:
                    summary = summary[: ctx.deps.summarization_threshold] + "... [truncated]"
            if summary:
                line += f"\n    {summary}"
            out_lines.append(line)

        results = "\n".join(out_lines)
        return f"Academic search results for '{topic}':\n{results}"

    @agent.tool
    async def cache_get(
        ctx: RunContext[ResearchDependencies],
        key: str
    ) -> str:
        """Return cached summary JSON (string) if present, else an empty string."""
        res = _cache.cache_get(key)
        return json.dumps(res) if res is not None else ""

    @agent.tool
    async def cache_set(
        ctx: RunContext[ResearchDependencies],
        key: str,
        value: dict
    ) -> str:
        _cache.cache_set(key, value)
        return "OK"

    @agent.tool
    async def summarize_document_tool(
        ctx: RunContext[ResearchDependencies],
        doi: str,
        condensation_config: dict,
        max_tokens: int = 2000,
    ) -> str:
        out = _cache.summarize_document(doi, condensation_config, max_tokens=max_tokens)
        return json.dumps(out)

    @agent.tool
    async def search_documentation(
        ctx: RunContext[ResearchDependencies],
        technology: str,
        topic: str
    ) -> str:
        print("📖 Searching documentation:", technology, "-", topic)
        query = f"{technology} {topic} site:docs OR site:documentation OR official"
        tool = _get_duckduckgo_tool()(max_results=3)
        func = tool.function
        if getattr(tool, 'takes_ctx', False):
            results = await func(ctx, query)
        else:
            results = await func(query)
        if isinstance(results, str) and len(results) > ctx.deps.summarization_threshold:
            if ctx.deps.enable_summarization:
                results = summarize_text(results, ctx.deps.summarization_threshold)
            else:
                results = results[: ctx.deps.summarization_threshold] + "... [truncated]"
        return f"Documentation search for '{technology} {topic}':\n{results}"

    return agent


def summarize_text(text: str, max_chars: int = 800) -> str:
    """Very small deterministic summarizer used to reduce token usage.

    This is intentionally lightweight and does not call the LLM. It extracts
    the first few sentences up to max_chars. It's opt-in via
    ResearchDependencies.enable_summarization.
    """
    import re

    # Split into sentences (very simple heuristic)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    summary = []
    total = 0
    for s in sentences:
        if total + len(s) > max_chars:
            break
        summary.append(s)
        total += len(s) + 1

    if not summary:
        # Fallback to hard truncation
        return text[:max_chars] + '... [truncated]'

    out = ' '.join(summary)
    if len(out) < len(text):
        out = out.strip() + '... [summary]'
    return out


def _find_sentence_with(text: str, term: str) -> str | None:
    if not text or not term:
        return None
    import re
    # split into sentences and find one containing the term (case-insensitive)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    term_l = term.lower()
    for s in sentences:
        if term_l in s.lower():
            return s.strip()
    return None


def generate_provenance(final: FinalAnswer, deps: ResearchDependencies) -> Dict[str, Any]:
    """Generate a provenance map: fingerprint -> metadata including claims.

    For each collected source that has a fingerprint, search the final.answer
    and final.reasoning for mentions of the source title, DOI, or URL and
    record the sentence(s) where the mention occurred.
    """
    prov: Dict[str, Any] = {}
    answer_text = (final.answer or "") + "\n" + (final.reasoning or "")
    for src in deps.sources_collected or []:
        fp = getattr(src, "fingerprint", None)
        if not fp:
            continue
        claims = []
        # search by title, DOI, URL
        terms = [src.title or ""]
        # try DOI in src.meta if present
        doi = None
        if isinstance(src.meta, dict):
            doi = src.meta.get("DOI") or src.meta.get("doi")
        if doi:
            terms.append(doi)
        if src.url:
            terms.append(src.url)

        for t in terms:
            if not t:
                continue
            s = _find_sentence_with(answer_text, t)
            if s:
                claims.append(s)

        prov[fp] = {
            "title": src.title,
            "url": src.url,
            "confidence": src.confidence,
            "summary_meta": src.meta,
            "claims": claims,
        }
    return prov


def _make_claim_id(claim_text: str) -> str:
    import hashlib
    if not claim_text:
        return ""
    h = hashlib.sha256(claim_text.encode("utf-8")).hexdigest()
    # short id for readability
    return h[:12]


def format_provenance_report(final: FinalAnswer, deps: ResearchDependencies) -> Dict[str, Any]:
    """Create a provenance report with both fingerprint->metadata and claim_id->fingerprints maps.

    Output shape:
      {
        "by_fingerprint": { fp: { ... , "claims": [...] } },
        "by_claim_id": { claim_id: { "claim": text, "fingerprints": [fp,...] } }
      }
    """
    by_fp = generate_provenance(final, deps)
    by_claim: Dict[str, Dict[str, Any]] = {}
    for fp, meta in by_fp.items():
        for claim in meta.get("claims", []) or []:
            cid = _make_claim_id(claim)
            if cid not in by_claim:
                by_claim[cid] = {"claim": claim, "fingerprints": []}
            if fp not in by_claim[cid]["fingerprints"]:
                by_claim[cid]["fingerprints"].append(fp)

    return {"by_fingerprint": by_fp, "by_claim_id": by_claim}


def apply_provenance_to_final(final: FinalAnswer, deps: ResearchDependencies) -> None:
    """Attach a formatted provenance report to the FinalAnswer.provenance field in-place."""
    report = format_provenance_report(final, deps)
    final.provenance = report



# ============================================================================
# Async Research Function with Looping
# ============================================================================

async def research_question(
    question: str,
    max_iterations: int = 10,
    min_confidence: int = 8,
    model: str = "openai:gpt-4o",
    enable_summarization: Optional[bool] = None,
) -> FinalAnswer:
    """
    Research a question with iterative refinement until high confidence.
    
    Args:
        question: The question to research
        max_iterations: Maximum research iterations
        min_confidence: Minimum confidence level (0-10) to stop
        model: Model to use (can be ramalama served model URL)
    
    Returns:
        FinalAnswer with evidence and reasoning
    """
    print("\n" + "="*80)
    print("🔬 RESEARCH AGENT STARTING")
    print("" + "="*80)
    print(f"Question: {question}")
    print(f"Max iterations: {max_iterations}")
    print(f"Target confidence: {min_confidence}/10")
    print(f"{'='*80}\n")
    
    deps = ResearchDependencies(
        max_iterations=max_iterations,
        min_confidence=min_confidence
    )
    # Determine summarization behavior. If the caller explicitly set
    # enable_summarization (True/False), use that. If it's None, enable
    # summarization heuristically for local RamaLama / small models to
    # avoid exceeding model context windows.
    # Decide whether summarization should be enabled and log the choice so
    # users can see whether it was an explicit override or a heuristic.
    chosen, reason = should_enable_summarization(model, enable_summarization)
    deps.enable_summarization = chosen
    logger.info("Summarization enabled=%s (%s)", chosen, reason)
    
    # Create agent for requested model (OpenAI by default or a ramalama URL)
    agent = create_agent(model)

    # Select a concise prompt when using a local RamaLama HTTP endpoint to
    # avoid exceeding the model's context window on smaller local models.
    if isinstance(model, str) and model.startswith(('http://', 'https://')):
        prompt = (
            f"Research: {question}\n"
            f"Use tools: web_search, analyze_source, record_thought.\n"
            f"After each step, record a short thought with confidence (0-10) and next action.\n"
            f"Stop when confidence >= {min_confidence} or iterations >= {max_iterations}."
        )
    else:
        prompt = (
            f"Research this question thoroughly: {question}\n\n"
            "Follow this process:\n"
            "1. First, search the web for current information\n"
            "2. Record sources and your confidence in them\n"
            "3. After each search, record your thoughts including:\n"
            "   - What you learned\n"
            "   - Your current confidence level (0-10)\n"
            "   - What you still need to investigate\n"
            f"4. If confidence < {min_confidence}, continue researching with more specific queries\n"
            "5. Cross-reference information from multiple sources\n"
            f"6. Only provide final answer when confidence >= {min_confidence} OR iterations >= {max_iterations}\n\n"
            "Begin your research now!"
        )

    # Run the agent - it will loop internally via tools
    result = await agent.run(prompt, deps=deps)
    
    # Add collected sources to the final answer
    final = result.output
    final.evidence = deps.sources_collected or []
    
    print("\n" + "="*80)
    print("✅ RESEARCH COMPLETE")
    print("" + "="*80)
    print(f"Iterations used: {deps.iteration_count}/{max_iterations}")
    print(f"Sources collected: {len(deps.sources_collected or [])}")
    print(f"Final confidence: {final.confidence}/10")
    print(f"Certainty level: {final.certainty_level}")
    print("" + "="*80 + "\n")
    
    return final



# ============================================================================
# Synchronous Wrapper
# ============================================================================

def research_question_sync(
    question: str,
    max_iterations: int = 10,
    min_confidence: int = 8,
    model: str = "openai:gpt-4o"
) -> FinalAnswer:
    """Synchronous wrapper for research_question"""
    return asyncio.run(research_question(question, max_iterations, min_confidence, model))



# ============================================================================
# Main Example
# ============================================================================

async def main():
    """Example usage of the research agent"""
    
    # Example 1: Scientific question
    print("\n" + "="*80)
    print("EXAMPLE 1: Scientific Research")
    print("="*80)
    
    result1 = await research_question(
        "What is the current scientific consensus on the effectiveness of mRNA vaccines?",
        max_iterations=8,
        min_confidence=8
    )
    
    print("\n📋 FINAL ANSWER:")
    print(f"Answer: {result1.answer}\n")
    print(f"Confidence: {result1.confidence}/10 ({result1.certainty_level})")
    print(f"\nReasoning: {result1.reasoning}\n")
    print(f"Evidence sources: {len(result1.evidence)}")
    for i, source in enumerate(result1.evidence, 1):
        print(f"  {i}. {source.title} (confidence: {source.confidence}/10)")
        if source.url:
            print(f"     {source.url}")
    
    # Example 2: Technical question
    print("\n" + "="*80)
    print("EXAMPLE 2: Technical Documentation Research")
    print("="*80)
    
    result2 = await research_question(
        "How does Pydantic AI handle tool calling with dependencies?",
        max_iterations=6,
        min_confidence=8
    )
    
    print("\n📋 FINAL ANSWER:")
    print(f"Answer: {result2.answer}\n")
    print(f"Confidence: {result2.confidence}/10 ({result2.certainty_level})")

if __name__ == "__main__":
    asyncio.run(main())
