# Personal Research Agent 🔬

A sophisticated research agent built with [Pydantic AI](https://github.com/pydantic/pydantic-ai), [RamaLama](https://github.com/containers/ramalama), and ethical open-source tools. This agent iteratively researches questions using web search, academic papers, and documentation until it achieves high confidence in its answers.

## Features ✨

- **🔄 Iterative Research Loop**: Continues searching and refining until reaching high confidence (8+/10)
- **📚 Multiple Information Sources**: Web search, academic papers, technical documentation
- **🎯 Evidence-Based Answers**: Collects and cites sources with confidence levels
- **🧠 Transparent Reasoning**: Shows thinking process and iteration progress
- **🐳 Local Model Support**: Works with RamaLama-served models (no API keys needed!)
- **⚡ Fast or Powerful**: Choose from lightweight to powerful models based on needs
- **🔒 Ethical & Open**: Uses open-source tools and models where possible

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Research Agent (Pydantic AI)           │
│  ┌────────────────────────────────────────────┐    │
│  │  Core Loop (until confidence >= 8/10)      │    │
│  │  1. Search web/papers/docs                 │    │
│  │  2. Analyze and record sources             │    │
│  │  3. Update confidence level                │    │
│  │  4. Determine next action                  │    │
│  │  5. Repeat if needed                       │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                      │
                      ├─────► DuckDuckGo Search (Web)
                      ├─────► Academic Papers (arXiv, PubMed)
                      ├─────► Documentation Sites
                      └─────► LLM (OpenAI or RamaLama)
                                    │
                                    └─► Local models via RamaLama
                                        (granite, deepseek, etc.)
```

## Installation

### 1. Install with uv (recommended)

Use Astral's `uv` as the project manager for fast, reproducible installs. Install `uv` (one-time), then create the project environment and install dependencies:

```bash
# Install uv (one-time)
# Option A: standalone installer (macOS / Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Option B: with pip (user or inside a small bootstrap venv)
python3 -m pip install --user uv

# From the project root, create/ensure the project venv and install dependencies
cd /var/home/geo/Documents/MyAi
uv venv
uv sync   # install from pyproject.toml / lockfile

# You can also add packages interactively
uv add pydantic_ai duckduckgo-search
```

If you prefer the classic venv+pip workflow, the old commands still work (install the package from the current directory):

```bash
cd /var/home/geo/Documents/MyAi
python3 -m venv venv
source venv/bin/activate
pip install .
```

### 2. Install RamaLama (Optional - for local models)

#### On Linux:
```bash
# Using pip
pip install ramalama

# Or using your package manager
# Fedora/RHEL
sudo dnf install ramalama

# Ubuntu/Debian (if available)
sudo apt install ramalama
```

#### Verify Installation:
```bash
ramalama --version
```

### 3. Set Up API Keys (if using cloud models)

For OpenAI:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

For Anthropic:
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

For Google:
```bash
export GOOGLE_API_KEY="your-api-key-here"
```

## Quick Start

### Using OpenAI (requires API key)

Run the scripts inside the project's environment for reproducibility. With `uv`, use `uv run`:

```bash
# Interactive mode
uv run python research_agent_example.py --mode interactive

# Single question
uv run python research_agent_example.py --question "What is quantum entanglement?"

# Run all examples
uv run python research_agent_example.py --mode all
```

### Using RamaLama (local, no API key needed)


#### running with RamaLama hosted on the host (recommended for containers)

When running the project inside a container we assume RamaLama is provided
externally (for example as a host container). The recommended flow is:

1. Start RamaLama on the host (outside the agent container):

```bash
# Start a host-side RamaLama server for the model you want to use
ramalama serve gpt-oss:20b --port 8080 --name research-agent-gpt-oss
```

2. Run the agent container and tell it to use RamaLama. When the agent is
     running inside a container and `--use-ramalama`, it will assume the RamaLama API is already available at the configured host/port.

```bash
# Run the agent container (no podman socket mount required for this flow)
podman run --rm -it \
    --env RAMALAMA_PORT=8080 \
    --env RAMALAMA_MODEL=gpt-oss:20b \
    myai-ramalama --use-ramalama --ramalama-model gpt-oss:20b
```

Notes:
- If you do want the agent to be able to spawn host-side containers (not the
    default for in-container runs), mount the host podman socket into the
    container — but this is optional for the common case where RamaLama is
    already running on the host.
- Optionally expose RamaLama port to host with `-p 8080:8080` on the RamaLama
    server if you need external access.

Networking tip — run both containers on a shared user network
------------------------------------------------------------
If you prefer the agent and RamaLama to communicate over a container
network (so the agent can reach the RamaLama container by name), create a
user-defined podman network and attach both containers to it. Example:

```bash
# Create a user network
podman network create myai-net

# Start RamaLama on that network (container name will be reachable as 'ramalama')
ramalama serve --network=myai-net --port 8080 --name research-agent-gpt-oss gpt-oss:20b


# Run the agent on the same network and point it at the ramalama container
podman run --rm -it --network myai-net \
    --env RAMALAMA_HOST=ramalama \
    --env RAMALAMA_PORT=8080 \
    --env RAMALAMA_MODEL=gpt-oss:20b \
    myai-ramalama --use-ramalama --ramalama-model gpt-oss:20b
```

This makes the agent call `http://ramalama:8080/v1` which resolves to the
RamaLama container on the shared `myai-net` network. This avoids localhost
port mapping and is a reliable pattern for multi-container setups.

#### running agent on host 

You can install RamaLama with `uv` or `pip`. Example using `uv`:

```bash
# Install RamaLama into the project env
uv add ramalama

# Pull a model
ramalama pull granite

# Run the research agent using the project environment
uv run python research_agent_example.py --use-ramalama --ramalama-model granite

# List available models
uv run python research_agent_example.py --show-models
```

Fallback with pip:

```bash
pip install ramalama
ramalama pull granite
python research_agent_example.py --use-ramalama --ramalama-model granite
```

## Usage Examples

### Example 1: Scientific Research

```python
from research_agent import research_question
import asyncio

async def main():
    result = await research_question(
        question="What is the current scientific consensus on dark matter?",
        max_iterations=10,
        min_confidence=8
    )
    
    print(f"Answer: {result.answer}")
    print(f"Confidence: {result.confidence}/10")
    print(f"Sources: {len(result.evidence)}")

asyncio.run(main())
```

### Example 2: Technical Documentation

```python
result = await research_question(
    question="How does dependency injection work in FastAPI?",
    max_iterations=8,
    min_confidence=8
)
```

### Example 3: Using RamaLama

```python
from ramalama_config import RamaLamaConfig

# Start a local model
ramalama = RamaLamaConfig(model_name="granite", port=8080)
container_id = ramalama.serve(detached=True)

try:
    # Research with local model
    result = await research_question(
        question="Explain Docker containers vs VMs",
        model="http://localhost:8080/v1"
    )
finally:
    ramalama.stop()
```

## Command-Line Interface

Run the CLI inside the project environment. Recommended (uv):

```bash
# Interactive mode (default)
uv run python research_agent_example.py

# Specific examples
uv run python research_agent_example.py --mode scientific
uv run python research_agent_example.py --mode technical
uv run python research_agent_example.py --mode current

# Custom parameters
uv run python research_agent_example.py \
    --question "What are transformer models?" \
    --max-iterations 15 \
    --min-confidence 9

# Use RamaLama with specific model
uv run python research_agent_example.py \
    --use-ramalama \
    --ramalama-model deepseek \
    --mode technical
```

## RamaLama Model Recommendations

### Fast (for quick research)
- **Model**: `granite`
- **Size**: ~2GB
- **Best for**: Quick lookups, simple questions

```bash
ramalama pull granite
```

### Balanced (for technical research)
- **Model**: `granite-code:20b`
- **Size**: ~12GB
- **Best for**: Technical documentation, code questions

```bash
ramalama pull granite-code:20b
```

### Powerful (for complex reasoning)
- **Model**: `deepseek`
- **Size**: ~20GB+
- **Best for**: Complex analysis, multi-step reasoning

```bash
ramalama pull deepseek
```

## How It Works

### Research Loop

1. **Initial Query**: Agent receives a question
2. **Search Phase**: 
   - Searches web via DuckDuckGo
   - Searches academic papers (arXiv, PubMed, etc.)
   - Searches documentation sites
3. **Analysis Phase**:
   - Records sources with confidence levels
   - Analyzes information quality
   - Cross-references facts
4. **Confidence Check**:
   - If confidence >= 8/10: Provide final answer
   - If confidence < 8/10: Generate more specific queries and continue
   - If max iterations reached: Provide best answer available
5. **Final Answer**: Synthesizes findings with evidence and reasoning

### Agent Tools

#### `web_search(query)`
Searches the web using DuckDuckGo for current information.

#### `check_academic_papers(topic)`
Searches academic sources (arXiv, PubMed, Google Scholar).

#### `search_documentation(technology, topic)`
Searches official documentation sites.

#### `analyze_source(title, content, url, confidence)`
Records and analyzes a source of information.

#### `record_thought(observation, analysis, next_action, confidence)`
Records thinking process and current confidence level.

## Configuration

### Environment Variables

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-..."

# Google
export GOOGLE_API_KEY="..."

# RamaLama settings (optional)
export RAMALAMA_PORT=8080
export RAMALAMA_MODEL=granite
```

### Agent Parameters

```python
result = await research_question(
    question="Your question here",
    max_iterations=10,      # Maximum research loops
    min_confidence=8,        # Target confidence (0-10)
    model="openai:gpt-4o"   # Model to use
)
```

## Advanced Usage

### Using MCP (Model Context Protocol) Servers

```python
from pydantic_ai import Agent

# Agent with MCP servers for enhanced tools
research_agent = Agent(
    'openai:gpt-4o',
    mcp_servers=[
        # Add MCP servers for additional capabilities
        # e.g., filesystem access, database queries, etc.
    ]
)
```

### Custom Tools

```python
@research_agent.tool
async def custom_database_search(
    ctx: RunContext[ResearchDependencies],
    query: str
) -> str:
    """Search your custom database"""
    # Your custom logic here
    return results
```

### Integration with Logfire (Observability)

```python
import logfire

logfire.configure()
logfire.instrument_pydantic_ai()

# Now all agent runs are logged to Logfire
result = await research_question("Your question")
```

## Project Structure

```
MyAi/
├── research_agent.py              # Core research agent
├── research_agent_example.py      # Example usage & CLI
├── ramalama_config.py             # RamaLama integration
├── pyproject.toml                 # Project metadata & dependencies
├── pyproject.toml                 # Project metadata & dependencies
└── README.md                      # This file
```

## Troubleshooting

### RamaLama not found
```bash
# Install via pip
pip install ramalama

# Or check installation
which ramalama
```

### Model fails to start
```bash
# Check running models
ramalama ps

# Stop all models
ramalama stop --all

# Check logs
podman logs <container-id>
```

### Out of memory
- Use a smaller model (e.g., `granite` instead of `deepseek`)
- Increase system swap space
- Use cloud API instead (OpenAI, Anthropic)

### API rate limits
- Reduce `max_iterations`
- Add delays between searches
- Use RamaLama local models (no rate limits!)

## Ethical Considerations

This agent is designed with ethics in mind:

1. **Transparency**: Shows all sources and confidence levels
2. **Accuracy**: Requires high confidence before providing answers
3. **Privacy**: Can run fully local with RamaLama (no data sent to APIs)
4. **Open Source**: Built on open-source tools and frameworks
5. **Fair Use**: Respects robots.txt and rate limits

## Contributing

Improvements welcome! Key areas:

- [ ] Additional source types (Wikipedia, arXiv direct API)
- [ ] PDF document parsing
- [ ] Citation formatting (APA, MLA, Chicago)
- [ ] Export to Markdown/HTML
- [ ] Multi-language support
- [ ] Voice interface integration

## License

MIT License - see LICENSE file for details

## Acknowledgments

- [Pydantic AI](https://github.com/pydantic/pydantic-ai) - Agent framework
- [RamaLama](https://github.com/containers/ramalama) - Local model serving
- [DuckDuckGo](https://duckduckgo.com) - Privacy-focused search
- MCP Protocol - Model Context Protocol standard


---

**Built with ❤️ using ethical, open-source AI tools**


### TODO

- [] Implement Dedicated Academic Retrieval Agent for Context Provenance

    The goal is to replace generalized web search with a specialized Academic Retrieval Agent that surfaces high-quality, peer-reviewed literature, capturing structured metadata essential for long-context RAG and summarization.

    1. Integrate Prioritized Academic API Backends

    Switch the default search behavior to prioritize structured academic context retrieval, ensuring provenance via canonical identifiers (DOI, PMID).

        Core API Selection: Integrate APIs for structured literature retrieval: PubMed/Europe PMC (biomedical/life sciences), CrossRef/DataCite (DOI resolution and metadata), and Semantic Scholar (citation graphs/quality signals).

        Search and Aggregation: Develop a unified search utility that queries these services simultaneously or sequentially, prioritizing results that contain a Digital Object Identifier (DOI) or a PubMed ID (PMID).

        Ethical Sourcing: Ensure all web services and tools used adhere to open-source licensing and ethical API usage policies, maintaining the open-source ethos.

    2. Implement Context Quality Filtering and Fallback

    Introduce robust filtering to ensure only high-quality, relevant documents are passed to the downstream context condensation pipeline.

        Mandatory Filters: Apply strict filtering rules to rank and select results:

            Peer-Reviewed Flag: Strongly prefer sources explicitly marked as peer-reviewed.

            Publication Date Window: Filter results by a relevant publication date range (e.g., last 5 years) to ensure currency.

            Quality & Impact Metrics: Utilize available signals such as citation count, journal quartile, or venue quality score to boost high-impact literature.

            Open Access Preference: Prioritize Open Access (OA) versions for simplified and ethical PDF fetching.

        Controlled Fallback: Only if the primary academic search returns insufficient or no peer-reviewed results should a controlled fallback to generalized web search (duckduckgo) be executed, ensuring this is tracked for context quality assessment.

- [ ] Build the RAG/Summarization Context Condensation Pipeline

    1. Implement a pipeline that proactively reduces the required context length while preserving critical semantic information, acting as the primary mechanism for mitigating the Long-Context Performance Cliff identified in the analysis.

        Chunking & Indexing: Chunk lengthy source documents (e.g., papers, transcripts) into semantically coherent blocks. Compute high-quality embeddings (using Sentence-Transformers, BGE, or comparable models) and index them in a scalable, high-throughput vector store (e.g., FAISS, Annoy, or RedisVector).

        Retrieval & Iterative Condensation: On a user query, perform a top-k semantic retrieval to fetch the most relevant chunks. The retrieved text must then be passed through a high-efficiency, multi-step summarizer (Extractive → Abstractive) to produce a single, concise context summary that reliably fits within a constrained token budget (e.g., ≤8K tokens), thereby focusing the LLM's attention.

        Provenance and Source Tracking: Design the retrieval and summarization process to strictly preserve the source DOI and chunk boundaries of the condensed context to ensure provenance and allow the agent to cite original documents, a critical capability for long-context reasoning.

    2. Implement Aggressive & Fingerprinted Cache Strategy

    To address the high computational cost of the RAG/summarization pipeline and mitigate latency, a persistent caching layer is mandatory.

        Persistent Summary Cache: Implement a persistent cache layer (e.g., Redis, S3) keyed by a composite identifier: DOI + Model_ID + Condensation_Prompt_Fingerprint. This ensures that context condensation is treated as a deterministic, reproducible process.

        Cache Invalidation Logic: Implement robust cache invalidation. Summaries should be reused for subsequent runs unless there is a change in the input document (DOI content), the underlying summarization model, or the specific prompt/configuration used for the condensation process.

        Agent Utility Exposure: Expose the following critical utilities to the core agent logic to enable dynamic context management:

            summarize_document(doi, condensation_config, max_tokens)

            cache_get(doi, fingerprint)

            cache_set(doi, fingerprint, summary_text)

        Prioritize Modularity: Design the system with a clear separation of concerns, ensuring that the Embedding Backend, the Vector Store, and the Summarization Engine are modular, pluggable components. This allows for rapid swapping to newer, more efficient open-source techniques (e.g., Q6 KV Cache-optimized models or different summarization models) without altering the main agent's core reasoning loop.

    3. Integrate with LLM Deployment Strategy (Context-Aware Routing)

    Ensure the developed pipeline is integrated with an LLM deployment strategy that acknowledges the constraints of VRAM and KV Cache scaling.

        Context Budget Enforcement: The Condensation Layer must enforce a strict output token limit to ensure the final prompt size is well within the 128K physical limit, preventing the "performance cliff" (Section III.B).

        Hybrid Deployment Hook: Design the agent loop to utilize the resulting context size to inform deployment decisions, aligning with the Hybrid Deployment Model recommended in the analysis (Section V.A):

            Low-Latency/Short-Context (GPU): If the condensed context is very short (e.g., ≤8K tokens), route the query to a low-latency, high-throughput GPU cluster (potentially running an 8B model with PagedAttention).

            Capacity-First/Ultra-Long Context (CPU/GGUF): If the agent determines a very large segment of the 128K window is required (e.g., for multi-document deep reasoning not fully served by the cache), route the request to a high-RAM CPU cluster running a highly-quantized 70B model (GGUF) to maximize capacity and cost efficiency for the latency-tolerant, analytical workload.

Notes:
- Add tests validating that evidence cited in final answers includes DOI/PMID and that cached summaries reduce token usage while retaining factual accuracy.
- Ensure provenance is recorded: which chunks/summaries supported which claims and their confidence scores.
- make sure the context limit of the dynamic model isnt reached through the agent process.