"""
Simple example demonstrating the research agent
Run this to see the agent in action!
"""
import asyncio
from research_agent import research_question


async def simple_demo():
    """
    Simple demonstration of the research agent.
    Change the question below to research anything you want!
    """
    
    print("\n" + "="*80)
    print("🔬 SIMPLE RESEARCH AGENT DEMO")
    print("="*80)
    print("\nThis demo will research a question and show you:")
    print("  • The iterative research process")
    print("  • Sources found and their confidence levels")
    print("  • The final answer with evidence")
    print("="*80 + "\n")
    
    # Change this question to research anything you want!
    question = "What is the difference between Docker and Podman?"
    
    print(f"Question: {question}\n")
    print("Starting research...\n")
    
    # Research with moderate settings (good for testing)
    result = await research_question(
        question=question,
        max_iterations=6,    # Fewer iterations for demo
        min_confidence=7     # Slightly lower confidence threshold
    )
    
    # Display the results
    print("\n" + "="*80)
    print("📋 FINAL ANSWER")
    print("="*80)
    print(f"\n{result.answer}\n")
    
    print(f"Confidence Level: {result.confidence}/10 ({result.certainty_level})")
    print(f"\nReasoning:")
    print(f"{result.reasoning}\n")
    
    if result.evidence:
        print(f"Evidence from {len(result.evidence)} sources:")
        for i, source in enumerate(result.evidence[:3], 1):  # Show first 3
            print(f"\n  Source {i}: {source.title}")
            print(f"  Confidence: {source.confidence}/10")
            if source.url:
                print(f"  URL: {source.url}")
    
    print("\n" + "="*80)
    print("✅ Demo complete!")
    print("="*80)


if __name__ == "__main__":
    # Make sure you have set OPENAI_API_KEY environment variable
    # Or edit research_agent.py to use a different model
    
    try:
        asyncio.run(simple_demo())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure you have:")
        print("1. Installed dependencies: pip install -r requirements.txt")
        print("2. Set API key: export OPENAI_API_KEY='your-key'")
        print("   OR use RamaLama: python research_agent_example.py --use-ramalama")
