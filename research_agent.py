"""
Personal Research Agent using Pydantic AI, RamaLama, and MCP tools
This agent researches questions using multiple sources and iterates until confident.
"""
import asyncio
import os
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
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
    sources_collected: list[ResearchSource] = None
    thoughts: list[ResearchThought] = None
    
    def __post_init__(self):
        if self.sources_collected is None:
            self.sources_collected = []
        if self.thoughts is None:
            self.thoughts = []


# ============================================================================
# Research Agent with Looping Logic
# ============================================================================

research_agent = Agent(
    'openai:gpt-4o',  # Can be swapped with ramalama served model
    deps_type=ResearchDependencies,
    output_type=FinalAnswer,
    retries=2,
    instructions="""You are a meticulous research assistant that finds definitive answers.

Your research process:
1. Break down complex questions into searchable components
2. Gather evidence from multiple reliable sources
3. Cross-reference information to verify accuracy
4. Identify contradictions or gaps in knowledge
5. Continue researching until you have HIGH confidence (8+ out of 10)
6. Synthesize findings into a clear, evidence-based answer

When researching:
- Use web search to find recent, authoritative information
- Look for primary sources and academic papers when possible
- Cross-verify facts across multiple sources
- Note any conflicting information
- Be transparent about uncertainty
- Keep searching until confidence is high or max iterations reached

IMPORTANT: For each iteration, provide a thought process showing:
- What you've learned
- Your current confidence level
- What you still need to investigate
""",
)


@research_agent.tool
async def web_search(ctx: RunContext[ResearchDependencies], query: str) -> str:
    """
    Search the web using DuckDuckGo for current information.
    Use this to find recent data, news, facts, and documentation.
    
    Args:
        query: The search query (be specific for best results)
    """
    print(f"🔍 Searching web: {query}")
    
    # Use the DuckDuckGo tool from pydantic-ai common tools
    results = await duckduckgo_search_tool()(query)
    
    # Track that we performed a search
    ctx.deps.iteration_count += 1
    
    return f"Web search results for '{query}':\n{results}"


@research_agent.tool
async def analyze_source(
    ctx: RunContext[ResearchDependencies],
    title: str,
    content: str,
    url: Optional[str],
    confidence: int
) -> str:
    """
    Record and analyze a source of information.
    Use this to save valuable information you find.
    
    Args:
        title: Brief description of the source
        content: Key information from the source
        url: URL if available
        confidence: Your confidence in this source (0-10)
    """
    source = ResearchSource(
        title=title,
        content=content,
        url=url,
        confidence=confidence
    )
    ctx.deps.sources_collected.append(source)
    
    print(f"📚 Recorded source: {title} (confidence: {confidence}/10)")
    
    return f"Source recorded. Total sources: {len(ctx.deps.sources_collected)}"


@research_agent.tool
async def record_thought(
    ctx: RunContext[ResearchDependencies],
    observation: str,
    analysis: str,
    next_action: str,
    confidence: int
) -> str:
    """
    Record your thinking process and current confidence level.
    Use this after each research step to track progress.
    
    Args:
        observation: What you learned in this iteration
        analysis: Your analysis of the information
        next_action: What you plan to investigate next
        confidence: Current confidence level (0-10)
    """
    thought = ResearchThought(
        observation=observation,
        analysis=analysis,
        next_action=next_action,
        confidence=confidence
    )
    ctx.deps.thoughts.append(thought)
    
    print(f"💭 Iteration {ctx.deps.iteration_count}: Confidence {confidence}/10")
    print(f"   Next: {next_action}")
    
    # Check if we should continue
    should_stop = (
        confidence >= ctx.deps.min_confidence or 
        ctx.deps.iteration_count >= ctx.deps.max_iterations
    )
    
    if should_stop:
        status = "HIGH CONFIDENCE REACHED!" if confidence >= ctx.deps.min_confidence else "Max iterations reached"
        return f"Thought recorded. {status} Ready to provide final answer."
    
    return f"Thought recorded. Continue researching. (Iteration {ctx.deps.iteration_count}/{ctx.deps.max_iterations})"


@research_agent.tool
async def check_academic_papers(
    ctx: RunContext[ResearchDependencies],
    topic: str
) -> str:
    """
    Search for academic papers and research on a topic.
    Use this for scientific or technical questions.
    
    Args:
        topic: The research topic or question
    """
    print(f"📄 Searching academic sources: {topic}")
    
    # Search for academic content
    query = f"site:arxiv.org OR site:scholar.google.com OR site:pubmed.ncbi.nlm.nih.gov {topic}"
    results = await duckduckgo_search_tool()(query)
    
    ctx.deps.iteration_count += 1
    
    return f"Academic search results for '{topic}':\n{results}"


@research_agent.tool
async def search_documentation(
    ctx: RunContext[ResearchDependencies],
    technology: str,
    topic: str
) -> str:
    """
    Search official documentation for technical questions.
    Use this for software, API, or technical specification questions.
    
    Args:
        technology: The technology/product name (e.g., 'Python', 'Docker', 'AWS')
        topic: Specific topic or feature to research
    """
    print(f"📖 Searching documentation: {technology} - {topic}")
    
    # Search in documentation sites
    query = f"{technology} {topic} site:docs OR site:documentation OR official"
    results = await duckduckgo_search_tool()(query)
    
    ctx.deps.iteration_count += 1
    
    return f"Documentation search for '{technology} {topic}':\n{results}"


# ============================================================================
# Async Research Function with Looping
# ============================================================================

async def research_question(
    question: str,
    max_iterations: int = 10,
    min_confidence: int = 8,
    model: str = "openai:gpt-4o"
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
    print(f"\n{'='*80}")
    print(f"🔬 RESEARCH AGENT STARTING")
    print(f"{'='*80}")
    print(f"Question: {question}")
    print(f"Max iterations: {max_iterations}")
    print(f"Target confidence: {min_confidence}/10")
    print(f"{'='*80}\n")
    
    deps = ResearchDependencies(
        max_iterations=max_iterations,
        min_confidence=min_confidence
    )
    
    # Override model if using ramalama
    agent = research_agent
    if model.startswith("http://") or model.startswith("https://"):
        agent = agent.override(model=model)
    
    # Run the agent - it will loop internally via tools
    result = await agent.run(
        f"""Research this question thoroughly: {question}

Follow this process:
1. First, search the web for current information
2. Record sources and your confidence in them
3. After each search, record your thoughts including:
   - What you learned
   - Your current confidence level (0-10)
   - What you still need to investigate
4. If confidence < {min_confidence}, continue researching with more specific queries
5. Cross-reference information from multiple sources
6. Only provide final answer when confidence >= {min_confidence} OR iterations >= {max_iterations}

Begin your research now!""",
        deps=deps
    )
    
    # Add collected sources to the final answer
    final = result.output
    final.evidence = deps.sources_collected
    
    print(f"\n{'='*80}")
    print(f"✅ RESEARCH COMPLETE")
    print(f"{'='*80}")
    print(f"Iterations used: {deps.iteration_count}/{max_iterations}")
    print(f"Sources collected: {len(deps.sources_collected)}")
    print(f"Final confidence: {final.confidence}/10")
    print(f"Certainty level: {final.certainty_level}")
    print(f"{'='*80}\n")
    
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
    # Set your API key
    # For OpenAI: export OPENAI_API_KEY=your-key
    # Or use ramalama served model: http://localhost:8080/v1
    
    asyncio.run(main())
