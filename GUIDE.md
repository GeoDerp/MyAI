# Personal Research Agent - Complete Guide

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage Examples](#usage-examples)
5. [How It Works](#how-it-works)
6. [Using RamaLama](#using-ramalama)
7. [Advanced Features](#advanced-features)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)

---

## Quick Start

### 30-Second Setup

```bash
# 1. Clone/navigate to project
cd /var/home/geo/Documents/MyAi

# 2. Run setup script
chmod +x setup.sh
./setup.sh

# 3. Set API key (choose one option)
export OPENAI_API_KEY="your-key-here"
# OR use local model: ramalama pull granite

# 4. Run demo
python simple_demo.py
```

---

## Installation

### Prerequisites

- **Python 3.9+** (check with `python3 --version`)
- **pip** (Python package installer)
- **RamaLama** (optional, for local models)

### Method 1: Automated Setup (Recommended)

```bash
chmod +x setup.sh
./setup.sh
```

### Method 2: Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create config file
cp config.env.example .env
```

### Installing RamaLama (Optional)

For running models locally without API keys:

```bash
# Using pip
pip install ramalama

# OR on Fedora/RHEL
sudo dnf install ramalama

# Verify
ramalama --version
```

---

## Configuration

### API Keys

Edit `.env` file or set environment variables:

```bash
# OpenAI (recommended for best results)
export OPENAI_API_KEY="sk-..."

# Anthropic Claude (alternative)
export ANTHROPIC_API_KEY="sk-ant-..."

# Google Gemini (alternative)
export GOOGLE_API_KEY="..."
```

### Agent Settings

In `.env` file:

```ini
# Research settings
MAX_ITERATIONS=10        # How many research loops
MIN_CONFIDENCE=8         # Stop when confidence reaches this (0-10)
DEFAULT_MODEL=openai:gpt-4o  # Which model to use
```

---

## Usage Examples

### Example 1: Simple Demo

```bash
python simple_demo.py
```

This runs a single research query and shows the full process.

### Example 2: Interactive Mode

```bash
python research_agent_example.py --mode interactive
```

Ask multiple questions in a conversational interface.

### Example 3: Single Question (CLI)

```bash
python research_agent_example.py \
    --question "What is quantum entanglement?" \
    --max-iterations 10 \
    --min-confidence 8
```

### Example 4: Python Code

```python
from research_agent import research_question
import asyncio

async def main():
    result = await research_question(
        question="How does photosynthesis work?",
        max_iterations=8,
        min_confidence=8
    )
    
    print(f"Answer: {result.answer}")
    print(f"Confidence: {result.confidence}/10")
    
    for source in result.evidence:
        print(f"- {source.title} (confidence: {source.confidence}/10)")

asyncio.run(main())
```

### Example 5: Using RamaLama

```bash
# Pull a model first
ramalama pull granite

# Use with research agent
python research_agent_example.py \
    --use-ramalama \
    --ramalama-model granite
```

---

## How It Works

### Research Loop

```
┌─────────────────────────────────────┐
│ 1. Receive Question                 │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 2. Search Web/Papers/Docs           │
│    - DuckDuckGo search              │
│    - Academic papers                │
│    - Documentation sites            │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 3. Analyze Sources                  │
│    - Extract key information        │
│    - Rate confidence level          │
│    - Cross-reference facts          │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 4. Record Thought                   │
│    - What was learned               │
│    - Current confidence             │
│    - Next investigation step        │
└────────────┬────────────────────────┘
             │
             ▼
       ┌─────────────┐
       │ Confidence  │
       │  >= 8/10?   │
       └──┬──────┬───┘
          │      │
      Yes │      │ No
          │      │
          ▼      └──────────┐
    ┌─────────┐             │
    │  Stop   │             │
    │ & Report│             │
    └─────────┘             │
                            │
         ┌──────────────────┘
         │
         ▼
    ┌─────────────────────────────────┐
    │ Max Iterations Reached?         │
    └────┬───────────────────┬────────┘
         │                   │
     No  │               Yes │
         │                   │
         └───► Loop Back     └──► Stop & Report
               to Step 2          (with current
                                   confidence)
```

### Tools Available

1. **web_search(query)** - Search the web
2. **check_academic_papers(topic)** - Search academic sources
3. **search_documentation(technology, topic)** - Search docs
4. **analyze_source(...)** - Record a source
5. **record_thought(...)** - Record thinking process

---

## Using RamaLama

### Why Use RamaLama?

- ✅ **Free** - No API costs
- ✅ **Private** - Data stays local
- ✅ **No Rate Limits** - Research as much as you want
- ✅ **Offline** - Works without internet (after model download)
- ❌ **Slower** - Depends on your hardware
- ❌ **Less Capable** - Smaller models than GPT-4

### Recommended Models

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| granite | 2GB | ⚡⚡⚡ | ⭐⭐ | Quick lookups |
| granite-code:20b | 12GB | ⚡⚡ | ⭐⭐⭐ | Technical research |
| deepseek | 20GB+ | ⚡ | ⭐⭐⭐⭐ | Complex analysis |

### Setup RamaLama Models

```bash
# Show available models
ramalama list

# Pull a model
ramalama pull granite

# List pulled models
ramalama list

# Start serving (automatic in examples)
ramalama serve --port 8080 granite
```

### Use with Research Agent

```bash
# Command line
python research_agent_example.py --use-ramalama

# Or in Python
result = await research_question(
    question="Your question",
    model="http://localhost:8080/v1"
)
```

---

## Advanced Features

### 1. Custom Confidence Thresholds

```python
# Lower confidence (faster, less thorough)
result = await research_question(
    question="Quick fact check?",
    min_confidence=6  # Stop at 60% confidence
)

# Higher confidence (slower, more thorough)
result = await research_question(
    question="Critical medical information?",
    min_confidence=9  # Need 90% confidence
)
```

### 2. Limited Iterations

```python
# Quick research (max 5 loops)
result = await research_question(
    question="Quick question",
    max_iterations=5
)

# Deep research (max 20 loops)
result = await research_question(
    question="Complex topic",
    max_iterations=20
)
```

### 3. Multiple Models

```python
# Try with different models for comparison
models = [
    "openai:gpt-4o",
    "anthropic:claude-sonnet-4-0",
    "http://localhost:8080/v1"  # Local RamaLama
]

for model in models:
    result = await research_question(
        question="Same question",
        model=model
    )
    print(f"{model}: Confidence {result.confidence}/10")
```

### 4. MCP Integration (Advanced)

```python
from mcp_integration import create_research_agent_with_mcp

agent = create_research_agent_with_mcp(
    mcp_servers=[
        "http://localhost:8000/mcp",  # Filesystem access
        "http://localhost:8001/mcp",  # Database access
    ]
)
```

---

## Troubleshooting

### "Import Error: No module named 'pydantic_ai'"

```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### "OpenAI API Error: Invalid API Key"

```bash
# Check your key is set
echo $OPENAI_API_KEY

# If empty, set it
export OPENAI_API_KEY="sk-your-key-here"

# Or use RamaLama instead
python research_agent_example.py --use-ramalama
```

### "RamaLama not found"

```bash
# Install RamaLama
pip install ramalama

# Or use system package manager
sudo dnf install ramalama  # Fedora/RHEL
```

### "Out of Memory with RamaLama"

```bash
# Use smaller model
ramalama pull granite  # Instead of deepseek

# Or increase swap
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### "Agent gives low confidence answers"

- Increase `max_iterations` (allow more research time)
- Use more powerful model (gpt-4o instead of gpt-4o-mini)
- Check if sources are available for your topic
- Try rephrasing the question more specifically

---

## Best Practices

### 1. Question Formulation

**Good Questions:**
- "What is the scientific consensus on climate change in 2024?"
- "How does JWT authentication work in modern web apps?"
- "What are the differences between Docker and Podman?"

**Poor Questions:**
- "Tell me about stuff" (too vague)
- "What's the best?" (subjective)
- "How do I feel about X?" (opinion-based)

### 2. Balancing Speed vs. Thoroughness

| Use Case | max_iterations | min_confidence | Model |
|----------|---------------|----------------|-------|
| Quick fact | 5 | 6 | gpt-4o-mini |
| General research | 10 | 8 | gpt-4o |
| Critical info | 15 | 9 | gpt-4o |

### 3. Cost Management

```python
# Free: Use RamaLama
model = "http://localhost:8080/v1"

# Cheap: Use mini model with low iterations
model = "openai:gpt-4o-mini"
max_iterations = 5

# Quality: Use full model with high iterations
model = "openai:gpt-4o"
max_iterations = 15
```

### 4. Privacy Considerations

- Use **RamaLama** for sensitive questions (data stays local)
- Use **cloud APIs** for non-sensitive, complex questions
- Review `.env` file - never commit API keys!

---

## Common Use Cases

### Academic Research

```python
result = await research_question(
    "What are the latest developments in CRISPR gene editing?",
    max_iterations=12,
    min_confidence=9
)
```

### Technical Documentation

```python
result = await research_question(
    "How do I implement WebSocket authentication in FastAPI?",
    max_iterations=8,
    min_confidence=8
)
```

### Current Events

```python
result = await research_question(
    "What are the major AI policy changes in 2025?",
    max_iterations=10,
    min_confidence=7
)
```

### Fact Checking

```python
result = await research_question(
    "Is it true that drinking 8 glasses of water daily is necessary?",
    max_iterations=6,
    min_confidence=8
)
```

---

## Getting Help

- **GitHub Issues**: Report bugs or request features
- **Documentation**: [Pydantic AI Docs](https://ai.pydantic.dev)
- **Community**: [Pydantic Slack](https://logfire.pydantic.dev/docs/join-slack/)
- **RamaLama**: [RamaLama Docs](https://github.com/containers/ramalama)

---

## Next Steps

1. ✅ Run `simple_demo.py` to see it work
2. ✅ Try interactive mode with your own questions
3. ✅ Experiment with RamaLama for local models
4. ✅ Read the code to understand the architecture
5. ✅ Customize for your specific use case
6. ✅ Share feedback and improvements!

---

**Happy Researching! 🔬**
