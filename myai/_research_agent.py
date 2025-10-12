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
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool


# ============================================================================
# Data Models
# ============================================================================


class ResearchSource(BaseModel):
    """A source of information found during research"""
    title: str = Field(description="Title or description of the source")
    content: str = Field(description="Key information from the source")
    url: Optional[str] = Field(None, description="URL if applicable")
    confidence: int = Field(description="Confidence level 0-10 in this source", ge=0, le=10)


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
    if isinstance(model, str) and model.startswith(('http://', 'https://')):
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
        tool = duckduckgo_search_tool(max_results=3)
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
        source = ResearchSource(
            title=title,
            content=content,
            url=url,
            confidence=confidence
        )
        ctx.deps.sources_collected.append(source)
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
        query = f"site:arxiv.org OR site:scholar.google.com OR site:pubmed.ncbi.nlm.nih.gov {topic}"
        tool = duckduckgo_search_tool(max_results=3)
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
        return f"Academic search results for '{topic}':\n{results}"

    @agent.tool
    async def search_documentation(
        ctx: RunContext[ResearchDependencies],
        technology: str,
        topic: str
    ) -> str:
        print("📖 Searching documentation:", technology, "-", topic)
        query = f"{technology} {topic} site:docs OR site:documentation OR official"
        tool = duckduckgo_search_tool(max_results=3)
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



# ============================================================================
# Async Research Function with Looping
# ============================================================================

async def research_question(
    question: str,
    max_iterations: int = 10,
    min_confidence: int = 8,
    model: str = "openai:gpt-4o",
    enable_summarization: bool = False,
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
    # Wire in opt-in summarization
    deps.enable_summarization = enable_summarization
    
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
