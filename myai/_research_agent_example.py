"""
Example usage of the Research Agent with various configurations
"""
import asyncio
import argparse
from myai._research_agent import research_question, FinalAnswer
from myai._ramalama_config import RamaLamaConfig, print_model_recommendations


async def example_scientific_research():
    """Example: Research a scientific topic"""
    print("\n" + "=" * 80)
    print("SCIENTIFIC RESEARCH EXAMPLE")
    print("=" * 80)

    result = await research_question(
        question="What are the latest breakthroughs in quantum computing in 2024-2025?",
        max_iterations=10,
        min_confidence=8
    )

    display_result(result)
    return result


async def example_technical_documentation():
    """Example: Research technical documentation"""
    print("\n" + "=" * 80)
    print("TECHNICAL DOCUMENTATION EXAMPLE")
    print("=" * 80)

    result = await research_question(
        question="How does dependency injection work in Pydantic AI and what are best practices?",
        max_iterations=8,
        min_confidence=8
    )

    display_result(result)
    return result


async def example_current_events():
    """Example: Research current events"""
    print("\n" + "=" * 80)
    print("CURRENT EVENTS EXAMPLE")
    print("=" * 80)

    result = await research_question(
        question="What are the major AI policy developments globally in early 2025?",
        max_iterations=8,
        min_confidence=7
    )

    display_result(result)
    return result


async def example_with_ramalama(model_name: str = "granite", in_container: bool = False, max_iterations: int = 2):
    """Example: Use RamaLama instead of OpenAI"""
    print("\n" + "=" * 80)
    print(f"USING RAMALAMA MODEL: {model_name}")
    print("=" * 80)

    # Configure RamaLama client. When running inside a container we assume
    # a RamaLama server is already running on the host (in a separate
    # container) and the agent should not attempt to start or stop host
    # containers. In that case just use the configured base URL and skip
    # calling `serve()`.
    ramalama = RamaLamaConfig(model_name=model_name, port=8080)

    if in_container:
        print("\n[INFO] Running inside a container; assuming RamaLama is provided externally on the host.")
        result = await research_question(
            question="Explain the key differences between containers and virtual machines.",
            max_iterations=max_iterations,
            min_confidence=7,
            model=ramalama.base_url,
            enable_summarization=True
        )

        display_result(result)
        return result

    # Not running in a container: we may start/stop a host container for RamaLama
    try:
        container_id = ramalama.serve(detached=True)
        if container_id:
            print(f"Started RamaLama host container: {container_id}")

        # Wait a moment for the service to start
        print("\nWaiting for model to initialize...")
        await asyncio.sleep(5)

        # Use the local model with a limited number of iterations to keep requests small
        result = await research_question(
            question="Explain the key differences between containers and virtual machines.",
            max_iterations=max_iterations,
            min_confidence=7,
            model=ramalama.base_url  # Use RamaLama endpoint
        )

        display_result(result)

        return result

    finally:
        # Clean up
        print("\nStopping RamaLama service...")
        ramalama.stop()


def display_result(result: FinalAnswer):
    """Display research results in a formatted way"""
    print("\n" + "=" * 80)
    print("RESEARCH RESULTS")
    print("=" * 80)

    print("\n📋 ANSWER:")
    print(f"{result.answer}\n")

    print(f"📊 CONFIDENCE: {result.confidence}/10 ({result.certainty_level})")

    print("\n🧠 REASONING:")
    print(f"{result.reasoning}\n")

    if result.evidence:
        print(f"📚 EVIDENCE ({len(result.evidence)} sources):")
        for i, source in enumerate(result.evidence, 1):
            print(f"\n  {i}. {source.title}")
            print(f"     Confidence: {source.confidence}/10")
            if source.url:
                print(f"     URL: {source.url}")
            print(f"     Content: {source.content[:200]}...")

    print("\n" + "=" * 80)


async def interactive_mode():
    """Interactive mode for asking research questions"""
    print("\n" + "=" * 80)
    print("INTERACTIVE RESEARCH MODE")
    print("=" * 80)
    print("Ask research questions and get evidence-based answers!")
    print("Type 'quit' or 'exit' to stop.\n")
    import sys

    # Print TTY diagnostics to help debug cases where stdin isn't connected.
    try:
        print(f"[DEBUG] stdin.isatty()={sys.stdin.isatty()} stdout.isatty()={sys.stdout.isatty()}")
    except Exception:
        pass

    while True:
        try:
            # Use an explicit print+read so we can fallback to readline() when
            # input() behaves oddly under some container runtimes / uv wrappers.
            print("\n🔍 Your question: ", end="", flush=True)
            line = sys.stdin.readline()

            # EOF (e.g., no stdin attached) — exit cleanly with a message.
            if not line:
                print("\n\n[INFO] Stdin closed or not available; exiting interactive mode.")
                break

            question = line.strip()

            if question.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! 👋")
                break

            if not question:
                continue

            # Get research parameters
            print("\nResearch parameters:")
            try:
                print("  Max iterations (default 10): ", end="", flush=True)
                max_iter_line = sys.stdin.readline() or "\n"
                max_iter = int(max_iter_line.strip() or "10")

                print("  Min confidence 0-10 (default 8): ", end="", flush=True)
                min_conf_line = sys.stdin.readline() or "\n"
                min_conf = int(min_conf_line.strip() or "8")
            except Exception:
                max_iter = 10
                min_conf = 8

            # Perform research
            result = await research_question(
                question=question,
                max_iterations=max_iter,
                min_confidence=min_conf
            )

            display_result(result)

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please try again.")


async def run_all_examples():
    """Run all example scenarios"""
    print("\n" + "=" * 80)
    print("RUNNING ALL EXAMPLES")
    print("=" * 80)

    await example_scientific_research()
    await asyncio.sleep(2)

    await example_technical_documentation()
    await asyncio.sleep(2)

    await example_current_events()

    print("\n" + "=" * 80)
    print("ALL EXAMPLES COMPLETED")
    print("=" * 80)


def main():
    """Main entry point with CLI arguments"""
    parser = argparse.ArgumentParser(
        description="Personal Research Agent using Pydantic AI"
    )
    parser.add_argument(
        "--mode",
        choices=["scientific", "technical", "current", "interactive", "all"],
        default="interactive",
        help="Which example mode to run"
    )
    parser.add_argument(
        "--use-ramalama",
        action="store_true",
        help="Use RamaLama instead of OpenAI"
    )
    parser.add_argument(
        "--ramalama-model",
        default="granite",
        help="RamaLama model to use (default: granite)"
    )
    parser.add_argument(
        "--show-models",
        action="store_true",
        help="Show recommended models and exit"
    )
    parser.add_argument(
        "--question",
        type=str,
        help="Single question to research (non-interactive)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum research iterations"
    )
    parser.add_argument(
        "--min-confidence",
        type=int,
        default=8,
        help="Minimum confidence level (0-10)"
    )
    parser.add_argument(
        "--in-container",
        action="store_true",
        help="Indicate the program is running inside a container (set by Dockerfile/entrypoint)",
    )

    args = parser.parse_args()

    if args.in_container:
        # Small, explicit notice and a place to toggle container-specific behavior.
        print("[INFO] Running inside a container (flag --in-container provided)")

    if args.show_models:
        print_model_recommendations()
        return

    # Handle single question mode
    if args.question:
        result = asyncio.run(research_question(
            question=args.question,
            max_iterations=args.max_iterations,
            min_confidence=args.min_confidence
        ))
        display_result(result)
        return

    # Run examples based on mode
    if args.use_ramalama:
        # When running inside a container the --in-container flag is provided
        # by the entrypoint; pass it through so example_with_ramalama can
        # avoid attempting to spawn a host-side RamaLama container.
        asyncio.run(example_with_ramalama(args.ramalama_model, in_container=args.in_container))
    elif args.mode == "scientific":
        asyncio.run(example_scientific_research())
    elif args.mode == "technical":
        asyncio.run(example_technical_documentation())
    elif args.mode == "current":
        asyncio.run(example_current_events())
    elif args.mode == "interactive":
        asyncio.run(interactive_mode())
    elif args.mode == "all":
        asyncio.run(run_all_examples())


if __name__ == "__main__":
    main()
