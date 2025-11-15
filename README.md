# Deep Research Agent 🔬

A production-ready, academically rigorous Deep Research Agent built with a Hybrid Agent Architecture. This agent employs a sophisticated research methodology to deliver comprehensive, evidence-based answers.

## Features ✨

- **🧠 Hybrid Agent Architecture**: Combines the strengths of LangGraph, the STORM research framework, and specialized tools.
- **🔄 Deterministic & State-Managed Execution**: LangGraph ensures reliable, iterative research tasks.
- **📚 Rigorous Research Methodology**: Implements the STORM framework for comprehensive, multi-perspective question asking.
- **⏱️ Enforced Runtime SLA**: Every research run honors a 30-minute wall-clock budget (configurable via `MYAI_MAX_RUNTIME_SECONDS`) even on CPU-only deployments.
- **� LLM Sovereignty**: Supports self-hosted models via Ollama and `litellm` for maximum model choice and cost control.
- **🛠️ Specialized Tooling**: Integrates LlamaParse for PDF ingestion, Exa API for semantic search, and the Arxiv API for academic research.
- **✅ Ethical Resource Validation**: Startup checks verify that all external APIs are on the approved open-data allowlist (DuckDuckGo, arXiv, Crossref, Exa, RamaLama/local hosts).
- **� Production-Ready**: Served via a FastAPI application and containerized with Docker.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Deep Research Agent API (FastAPI)      │
└─────────────────────────────────────────────────────┘
                      │
┌─────────────────────────────────────────────────────┐
│              Orchestration (LangGraph)              │
│  ┌────────────────────────────────────────────┐    │
│  │  STORM Research Loop                       │    │
│  │  1. Plan Research                          │    │
│  │  2. Gather Information (Exa, Arxiv)        │    │
│  │  3. Process Content (LlamaParse)           │    │
│  │  4. Synthesize Report                      │    │
│  │  5. Reflect and Refine                     │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                      │
                      ├─────► LlamaParse (PDFs)
                      ├─────► Exa API (Semantic Search)
                      ├─────► Arxiv API (Academic Papers)
                      └─────► LLM (litellm -> Ollama)
                                    │
                                    └─► Self-hosted models (Llama 3, etc.)
```

## Installation

### 1. Install with uv (recommended)

Use Astral's `uv` as the project manager for fast, reproducible installs.

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# From the project root, create the project venv and install dependencies
uv sync
```

### 2. Set Up API Keys

This project requires API keys for LlamaParse and Exa.

```bash
export LLAMA_CLOUD_API_KEY="your-llama-cloud-api-key"
export EXA_API_KEY="your-exa-api-key"
```

### 3. Install RamaLama (Optional - for local models)

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

## Running the Agent

### 1. Start the API Server

```bash
uvicorn myai.api:app --reload
```

The API will be available at `http://localhost:8000`.

### 2. Use the API

You can send a POST request to the `/research` endpoint with a JSON body:

```json
{
  "topic": "The future of AI in scientific discovery"
}
```

### 3. Use Docker

Build and run the Docker container:

```bash
docker build -t deep-research-agent .
# Run API server (default)
docker run -p 8000:8000 -e LLAMA_CLOUD_API_KEY -e EXA_API_KEY deep-research-agent

# Run interactive CLI inside the container (ask questions from the prompt)
docker run -it --rm deep-research-agent cli

# Run the lightweight web UI (serves templates/index.html on port 8081)
docker run -p 8081:8081 --rm deep-research-agent webui
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

## Operational Safeguards

### Runtime budget (≤30 minutes per question)

- Both the FastAPI STORM agent and the legacy `research_agent` enforce a 30-minute wall-clock SLA per research question via a shared runtime guard.
- The limit covers CPU-only deployments—slow local LLMs automatically reduce iterations and will be interrupted once the budget is exhausted.
- Configure the budget with `MYAI_MAX_RUNTIME_SECONDS` (default `1800`). A graceful partial report is returned alongside `runtime_limited` metadata when the limit is reached.

### Ethical resource validation

- On startup, the API/web UI runs `myai.ethics.assert_resource_policy_or_raise()` which ensures every configured endpoint belongs to the approved open-data allowlist (DuckDuckGo, arXiv, Crossref, Exa, RamaLama/local hosts).
- Extend the allowlist via `MYAI_ALLOWED_RESOURCE_HOSTS="host1,host2"` when integrating additional vetted services.
- You can audit the current configuration locally:

```bash
python -m myai.ethics
```

The command prints the mapped hosts and exits non-zero if a host violates the policy.


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

2.  Run the agent container and tell it to use RamaLama.

When the agent runs inside a container and `--use-ramalama` is passed, it
assumes an OpenAI-compatible HTTP endpoint is available at the configured
host/port. The recommended production pattern is to run both containers on a
user network and point the agent at the RamaLama container by name.

```bash
# Create a user network (one-time)
podman network create myai-net

# Start RamaLama with automatic GPU detection and optimization
# The script probes AMD/ROCm, NVIDIA/CUDA, Intel iGPU, Apple Silicon, or CPU-only hosts and
# automatically selects the matching RamaLama runtime. It calculates available VRAM and
# falls back to CPU mode when dedicated memory is below 4GB while still leveraging large
# system RAM for inference. Layer offloading is tuned based on VRAM capacity:
# - < 512MB (integrated): CPU-only mode (--ngl 0)
# - 4-8GB: Minimal GPU offload (5-15 layers)
# - 8-16GB: Balanced GPU/CPU (15-35 layers)
# - 16GB+: Full GPU offload (35-41 layers)
bash scripts/start_ramalama_dynamic.sh granite4:small-h 8080 research-agent myai-net

# Or manually specify GPU layers if you know your hardware:
# Full GPU (requires 20GB+ VRAM):
# ramalama serve --network=myai-net --port 8080 --name research-agent granite4:small-h -d

# CPU-only (integrated GPUs or < 4GB VRAM):
# ramalama serve --network=myai-net --port 8080 --name research-agent --ngl 0 granite4:small-h -d 

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

## Web UI

A production-ready web UI with **background task support** is available to interact with the research agent.

### Key Features

- **Background Tasks**: Run long research jobs in the background and check back later
- **Task Status API**: Poll task status via `/status/<task_id>` endpoint
- **Automatic HTML Export**: Results saved to `/tmp/research_report.html` by default
- **Provenance Tracking**: Automatically writes provenance bundles alongside results

### Running the Web UI

1.  **Build the Docker image:**

    ```bash
    podman build -f Dockerfile.webui -t myai-webui
    ```

2.  **Run the container:**

    ```bash
        # Recommended: create a user network so the agent container can reach RamaLama by name
        podman network create myai-net || true

        # Run the web UI on the same network as your RamaLama server. The web UI listens on 8081.
        podman run -d --name myai-webui --network myai-net -p 8081:8081 myai-webui
    ```

3.  **Open your browser:**

    Navigate to `http://localhost:8081` to use the web UI.

### Using Background Tasks

The web UI now supports running research tasks in the background, allowing you to leave and come back when the task is complete.

**To use background mode:**
1. Enter your research question
2. Configure settings (iterations, RamaLama options, etc.)
3. **Check the "Run in background" checkbox**
4. Submit the form

You'll receive a Task ID and can:
- Check status at `/status/<task_id>` (returns JSON)
- View results at `/result/<task_id>` when complete
- Leave and return anytime - the task continues running

**Example workflow:**
```bash
# Submit a background task
curl -X POST "http://127.0.0.1:8081/" \
    -F 'question=What is quantum entanglement?' \
    -F 'max_iterations=10' \
    -F 'background=on'

# Returns: Task ID = abc-123-def

# Check status
curl "http://127.0.0.1:8081/status/abc-123-def"

# Get results when complete
curl "http://127.0.0.1:8081/result/abc-123-def"
```

### Production Deployment Considerations

**Important**: The web UI currently uses **in-memory task storage** and runs with a single Gunicorn worker to ensure task state consistency. This means:

- ✅ **Task persistence works correctly** across requests
- ⚠️ **Tasks are lost on container restart** 
- ⚠️ **Not suitable for high-concurrency loads** (single worker limitation)

**For production environments with high traffic**, consider:
1. **Implement Redis-backed task storage** to persist tasks across restarts and enable multi-worker deployment
2. **Use a proper task queue** like Celery or RQ for distributed task processing
3. **Scale horizontally** with multiple instances once shared state is implemented

**Timeout Considerations:**
- CPU-only LLM inference can take 5-10 minutes per request
- The Gunicorn timeout is set to 600 seconds (10 minutes)
- For very long research tasks, use background mode
- Monitor logs for `get_completion failed after 3 attempts` errors which indicate LLM timeouts

### Running with Docker Compose

The repository includes a `docker-compose.yml` for production deployment:

```bash
# Build and start all services
podman-compose up -d

# Or with docker-compose
docker-compose up -d
```

This starts:
- **webui**: Research agent web interface (port 8081)
- **myai-redis**: Redis for caching (port 6379, internal only)
- *Optional*: **ramalama**: Local LLM server (configure as needed)

Check health status:
```bash
curl http://localhost:8081/healthz
curl http://localhost:8081/readyz
```

Notes about running with a local RamaLama server
-----------------------------------------------
- The web UI can target a local RamaLama (OpenAI-compatible) server. Run RamaLama on the same user network so the web UI can reach it by container name. Example (podman):

```bash
# Start a RamaLama server on the user network and expose its OpenAI-compatible HTTP endpoint
podman run -d --name research-agent --network myai-net \
    quay.io/ramalama/intel-gpu:latest \
    ramalama serve --ngl 0 --image quay.io/ramalama/intel-gpu:latest --port 8080 --name research-agent granite4:small-h
# (Adjust image/model flags to match the model you pulled.)
```

- When you submit the form in the web UI and enable "Use RamaLama", point the Host/IP field at the RamaLama container name (for the example above use `research-agent`) and set the port (default 8080). The UI will reconfigure the LLM client at runtime and run the STORM research flow.

What the UI shows
------------------
- The web UI now renders structured outputs from the agent: a parsed `Plan` (if the model returned JSON), the `Questions` list, the synthesized `Report`, `Feedback` from a reflection pass, and any `Articles` gathered during the run.
- For debugging, the web UI container writes traces and normalized assistant content to `/tmp/myai_debug.log` inside the container. If something goes wrong, inspect that file to see the raw model responses, normalized assistant text, and whether an assistant JSON block was detected.
- **Background tasks**: Task status and results are stored in memory; for production deployments consider using Redis or a persistent task queue.

Quick test (form POST)
----------------------
You can exercise the same flow with curl (this mimics the web UI form):

```bash
curl -v -X POST "http://127.0.0.1:8081/" \
    -F 'question=Network test to research-agent' \
    -F 'max_iterations=2' \
    -F 'use_ramalama=on' \
    -F 'ramalama_host=research-agent' \
    -F 'ramalama_port=8080'
```

If RamaLama is running as `research-agent` on the `myai-net` network the UI will display the parsed plan and the final synthesized report from the model.

Inspect debug traces (inside the web UI container)
-------------------------------------------------
If you need to troubleshoot model connectivity or inspect raw LLM outputs, the web UI container writes detailed traces to `/tmp/myai_debug.log`.

Common commands:

```bash
# Print the whole debug log from the running container:
podman exec -it myai-webui cat /tmp/myai_debug.log

# Tail the last 200 lines (useful during active testing):
podman exec -it myai-webui tail -n 200 /tmp/myai_debug.log

# Stream web UI container logs (Flask stdout/stderr):
podman logs -f myai-webui

# Copy the file from the container onto the host for offline inspection:
podman cp myai-webui:/tmp/myai_debug.log ./myai_debug.log
```

## Production deployment

This repository includes a production-friendly `Dockerfile.webui` and a
`docker-compose.yml` to run the web UI in a containerized environment. The
entrypoint supports multiple modes and will run the Flask web UI under
Gunicorn in `webui` mode or the FastAPI app under Uvicorn in `server` mode.

Environment variables
- PORT: port the process listens on (default: 8081 for webui mode)
- HOST: network interface to bind to (default: 0.0.0.0)
- MYAI_DEBUG_FILE: optional path inside container to mirror debug traces (if set, logs are appended to this file in addition to stdout)
- MYAI_LOG_LEVEL: logging level (DEBUG, INFO, WARNING)
- **LLM_TIMEOUT**: LLM request timeout in seconds (default: 30)
- **LLM_RETRIES**: Maximum retry attempts for failed LLM calls (default: 2)

Provenance and integration environment variables
- `MYAI_PARTIAL_DIR` (optional): directory where the agent writes partial artifacts and provenance bundles when an external provenance store is not configured. Defaults to `/tmp`.
- `MYAI_RENDERED_OUTPUT` (optional): path to save a rendered HTML copy of web UI results. Defaults to `/tmp/research_report.html`.
- `LANGGRAPH_URL` (optional): if set, the agent will attempt to persist `ResearchSource` nodes and provenance to a LangGraph instance. If not set, the agent falls back to writing provenance bundles to `MYAI_PARTIAL_DIR`.
- `TORM_URL` (optional): a TORM service endpoint for multi-perspective question expansion. When absent a deterministic fallback is used.
- `EXA_API_KEY` (optional): API key for Exa; when present the `academic_retrieval` module may use Exa as a fallback for high-recall retrieval.
- `RAMALAMA_HOST`, `RAMALAMA_PORT` (optional): host and port for RamaLama (OpenAI-compatible) local model serving. When using the web UI you can toggle "Use RamaLama" and point the host/port at your RamaLama server.
- `LITELLM_BASE_URL`, `LITELLM_API_KEY` (optional): when using remote litellm-backends these may be used by the LLM manager.

Quick production run using docker-compose:

```bash
# Build and run the web UI (and optional RamaLama service if enabled)
podman-compose up -d --build

# Check health
curl http://localhost:8081/healthz

# View logs
podman-compose logs -f webui
```

If you prefer to run the web UI directly with Podman/Docker without compose:

```bash
# Build the image
podman build -f Dockerfile.webui -t myai-webui .

# Run the web UI on the myai-net network and map port 8081
podman network create myai-net || true
podman run --rm -d --name myai-webui --network myai-net -p 8081:8081 \
    -e PORT=8081 -e HOST=0.0.0.0 myai-webui webui
```

Security & production notes
- Run the container behind a reverse proxy (nginx, Traefik) for TLS and routing.
- Set resource limits (memory/cpu) appropriate for the model server and agent.
- Consider mounting a host directory for `MYAI_DEBUG_FILE` to retain logs outside the container.

Provenance behavior (fallback)
- When a provenance store (LangGraph) is not configured via `LANGGRAPH_URL`, the agent will write a provenance bundle JSON file for each research run into the directory configured by `MYAI_PARTIAL_DIR` (by default `/tmp`). The bundle includes recorded `ResearchSource` metadata, the final synthesized report, iteration logs, and a minimal execution trace to allow auditors to inspect how claims were produced.
- The web UI also writes a rendered HTML snapshot to `MYAI_RENDERED_OUTPUT` and, as a best-effort action, attempts to write a provenance bundle next to the HTML file or into `MYAI_PARTIAL_DIR` if a provenance store is not available.

Provenance bundle example
-------------------------
When LangGraph is not configured the agent writes a provenance bundle JSON file into `MYAI_PARTIAL_DIR`. A minimal example looks like this:

```json
{
    "question": "What causes X?",
    "timestamp": "20250101T123000Z",
    "sources": [
        {"title": "Paper A", "url": "https://doi.org/10.x/abc", "fetched_at": "20250101T122900Z", "id": "doi:10.x/abc"}
    ],
    "iterations": [
        {"step": 1, "notes": "searched CrossRef and web"}
    ],
    "final_report": "Summary text...",
    "final_confidence": 7
}
```

Quick env var reference
-----------------------

- `MYAI_PARTIAL_DIR` — directory for provenance bundles and partial outputs (default: `/tmp`).
- `MYAI_RENDERED_OUTPUT` — HTML snapshot path for the web UI (default: `/tmp/research_report.html`).
- `LANGGRAPH_URL` — optional LangGraph endpoint for persistent provenance. If set, the agent will attempt to persist sources there; otherwise provenance bundles are written to `MYAI_PARTIAL_DIR`.
- `TORM_URL` — optional TORM endpoint for question expansion.
- `EXA_API_KEY` — optional Exa API key used for high-recall retrieval.
- `RAMALAMA_HOST`, `RAMALAMA_PORT` — host/port for RamaLama local model serving (web UI toggle available).


Testing note
- Unit tests in `tests/` set `MYAI_PARTIAL_DIR` and `MYAI_RENDERED_OUTPUT` to temporary directories so they do not write to `/tmp` during CI runs. If you are running tests locally and want to inspect provenance bundles, set `MYAI_PARTIAL_DIR` to a directory you control.


What to look for
-----------------
- RAW_RESPONSE: A truncated representation of the full ModelResponse object returned by the LLM client.
- ASSISTANT_TEXT: A normalized assistant message (code fences stripped) derived from the RAW_RESPONSE.
- ASSISTANT_JSON_PRESENT: The agent detected a JSON object (usually the `plan`) inside the assistant text and parsed it.
- Connection warnings / errors: If you see messages like "Could not connect to LLM server" or litellm/InternalServerError traces, confirm the RamaLama container is running and attached to the same network as the web UI (`myai-net`).

If you'd like a convenience helper, see `scripts/show_debug.sh` which prints the last ~250 lines of the debug log from the running web UI container.

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
