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

1. Start RamaLama on the host (outside the agent container)

You can start RamaLama directly on the host. For production use we recommend
running RamaLama detached and exposing a stable port so the agent container
can reach it by hostname inside a user-defined network.

```bash
# Start a host-side RamaLama server for the model you want to use (detached)
ramalama serve gpt-oss:20b --port 8080 --name research-agent-gpt-oss -d
```

2. Run the agent container and tell it to use RamaLama.

When the agent runs inside a container and `--use-ramalama` is passed, it
assumes an OpenAI-compatible HTTP endpoint is available at the configured
host/port. The recommended production pattern is to run both containers on a
user network and point the agent at the RamaLama container by name.

```bash
# Create a user network (one-time)
podman network create myai-net

# Start RamaLama on that network (host container will be reachable as 'ramalama')
ramalama serve  --ngl 0 --image quay.io/ramalama/intel-gpu:latest  --network=myai-net --port 8080 --name research-agent granite4:small-h
#some usefull arguments --ngl 0 --image quay.io/ramalama/intel-gpu:latest 

# Optional: run Redis on the same network (recommended for production caching)
podman run -d --name myai-redis --network=myai-net \
    -v myai-redis-data:/data \
    docker.io/library/redis:7-alpine

# Run the agent on the same network and point it at the ramalama container.
podman build . -t myai-ramalama
podman run --rm -it --network=myai-net \
    --env RAMALAMA_PORT=8080 \
    --env RAMALAMA_MODEL=granite4:small-h \
    --env REDIS_URL=redis://myai-redis:6379/0 \
    --env RAMALAMA_HOST=research-agent \
    localhost/myai-ramalama:latest \
    --use-ramalama --ramalama-model granite4:small-h \
    --mode interactive --question "why is the sky blue"

Note: 
- The example runtime checks the Redis cache at startup (via
`cache.verify_redis_connection()`); setting `REDIS_URL` to a reachable Redis
instance enables condensation caching and improves performance.
-Optionally expose RamaLama port to host with `-p 8080:8080` on the RamaLama
    server if you need external access.
```


Networking tip — run both containers on a shared user network
------------------------------------------------------------
If you prefer the agent and RamaLama to communicate over a container
network (so the agent can reach the RamaLama container by name), create a
user-defined podman network and attach both containers to it. Example:

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
- [Crossref](https://www.crossref.org/) — Scholarly metadata and DOI registration service; useful for resolving DOIs, locating academic references, and retrieving citation metadata.
- [Redis](https://github.com/redis/redis)- Optional — caching / fingerprint store
---

**Built with ❤️ using ethical, open-source AI tools**
