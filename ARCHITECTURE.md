# Research Agent Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE                              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Simple Demo  │  │ Interactive  │  │  CLI Args    │             │
│  │  (simple_    │  │    Mode      │  │  (--question)│             │
│  │   demo.py)   │  │              │  │              │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│         │                  │                  │                     │
└─────────┼──────────────────┼──────────────────┼─────────────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       RESEARCH AGENT CORE                            │
│                      (research_agent.py)                             │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  ITERATIVE RESEARCH LOOP                                      │ │
│  │                                                               │ │
│  │  1. Receive Question                                          │ │
│  │  2. Search Information Sources                                │ │
│  │  3. Analyze & Record Sources                                  │ │
│  │  4. Record Thoughts & Update Confidence                       │ │
│  │  5. Check: Confidence >= 8/10 OR Max Iterations?              │ │
│  │     • YES → Generate Final Answer                             │ │
│  │     • NO  → Generate New Query & Loop Back to Step 2          │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  AGENT TOOLS (callable functions)                            │ │
│  │                                                               │ │
│  │  • web_search(query)                                          │ │
│  │  • check_academic_papers(topic)                               │ │
│  │  • search_documentation(technology, topic)                    │ │
│  │  • analyze_source(title, content, url, confidence)            │ │
│  │  • record_thought(observation, analysis, next_action, conf)   │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  INFORMATION     │ │     LLM MODEL    │ │   DATA MODELS    │
│    SOURCES       │ │                  │ │                  │
└──────────────────┘ └──────────────────┘ └──────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ • DuckDuckGo     │ │ ┌──────────────┐ │ │ • ResearchSource │
│   Web Search     │ │ │ Cloud APIs   │ │ │ • ResearchThought│
│                  │ │ │              │ │ │ • FinalAnswer    │
│ • Academic       │ │ │ • OpenAI     │ │ │ • Dependencies   │
│   Papers         │ │ │ • Anthropic  │ │ │                  │
│   (arXiv, etc)   │ │ │ • Google     │ │ └──────────────────┘
│                  │ │ └──────────────┘ │
│ • Documentation  │ │        OR        │
│   Sites          │ │ ┌──────────────┐ │
│                  │ │ │ RamaLama     │ │
│ • MCP Servers    │ │ │ (Local)      │ │
│   (optional)     │ │ │              │ │
│                  │ │ │ • granite    │ │
└──────────────────┘ │ │ • deepseek   │ │
                     │ │ • etc.       │ │
                     │ └──────────────┘ │
                     └──────────────────┘
```

## Data Flow

```
User Question
     │
     ▼
┌─────────────────────┐
│ Parse & Understand  │
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│ Initial Web Search  │◄──────┐
└─────────────────────┘       │
     │                        │
     ▼                        │
┌─────────────────────┐       │
│ Extract Information │       │
└─────────────────────┘       │
     │                        │
     ▼                        │
┌─────────────────────┐       │
│ Analyze & Score     │       │
│ (Confidence 0-10)   │       │
└─────────────────────┘       │
     │                        │
     ▼                        │
┌─────────────────────┐       │
│ Update Knowledge    │       │
│ Base & Confidence   │       │
└─────────────────────┘       │
     │                        │
     ▼                        │
     ┌─────────────┐          │
     │ Confidence  │          │
     │  >= 8/10?   │          │
     └─────────────┘          │
          │                   │
    Yes   │   No              │
          │   │               │
          │   └───────────────┘ Loop:
          │                     New Query
          ▼
┌─────────────────────┐
│ Generate Final      │
│ Answer with         │
│ Evidence & Reasoning│
└─────────────────────┘
     │
     ▼
Return to User
```

## Component Interactions

```
┌──────────────────────────────────────────────────────────────┐
│ research_agent.py (Core Logic)                               │
│                                                              │
│  • Agent definition with instructions                        │
│  • Tool definitions (@agent.tool decorators)                 │
│  • Data models (Pydantic)                                    │
│  • Main research_question() function                         │
└──────────────────────────────────────────────────────────────┘
                             │
                             │ uses
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ ramalama_config.py (Local Model Setup)                       │
│                                                              │
│  • RamaLamaConfig class                                      │
│  • Model recommendations                                     │
│  • Server start/stop utilities                               │
└──────────────────────────────────────────────────────────────┘
                             │
                             │ optionally uses
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ mcp_integration.py (Extended Capabilities)                   │
│                                                              │
│  • MCP server connection                                     │
│  • Additional tool discovery                                 │
│  • Filesystem/Database access                                │
└──────────────────────────────────────────────────────────────┘
```

## Usage Patterns

### Pattern 1: Quick Research
```
User → simple_demo.py → research_agent.py → OpenAI → Result
       (single Q)       (6 iterations)      (fast)    (7+/10)
```

### Pattern 2: Interactive Session
```
User → research_agent_example.py → research_agent.py → OpenAI → Result
       (multiple Qs)                (10 iterations)     (thorough) (8+/10)
       ↓ loop back                  ↓ loop back         ↓ loop     ↓
       ← next Q                     ← new queries       ← responses ← display
```

### Pattern 3: Local Model
```
User → research_agent_example.py → research_agent.py → RamaLama → Result
       (--use-ramalama)             (8 iterations)      (granite)   (7+/10)
                                                        (local)
```

### Pattern 4: Programmatic
```
Python Script → research_question() → Agent → LLM → FinalAnswer object
    │              (async function)     │      │      │
    │                                   │      │      └→ .answer
    │                                   │      │      └→ .confidence
    │                                   │      │      └→ .evidence[]
    │                                   │      │      └→ .reasoning
    └→ Process results                 ←──────┴──────┘
```

## File Dependency Graph

```
research_agent.py (core)
    ├── depends on: pydantic_ai, pydantic, DuckDuckGo
    └── provides: Agent, research_question(), data models

ramalama_config.py
    ├── depends on: subprocess
    └── provides: RamaLamaConfig, model recommendations

research_agent_example.py
    ├── depends on: research_agent.py, ramalama_config.py
    └── provides: CLI interface, examples

simple_demo.py
    ├── depends on: research_agent.py
    └── provides: Quick demo

mcp_integration.py
    ├── depends on: pydantic_ai.mcp, research_agent.py
    └── provides: MCP server integration

test_research_agent.py
    ├── depends on: research_agent.py, pytest
    └── provides: Unit tests
```

## State Management

```
ResearchDependencies (state container)
    │
    ├── max_iterations: int = 10
    ├── min_confidence: int = 8
    ├── iteration_count: int = 0
    │
    ├── sources_collected: List[ResearchSource]
    │   ├── ResearchSource 1 (title, content, url, confidence)
    │   ├── ResearchSource 2
    │   └── ResearchSource N
    │
    └── thoughts: List[ResearchThought]
        ├── ResearchThought 1 (observation, analysis, next_action, confidence)
        ├── ResearchThought 2
        └── ResearchThought N

Each tool call can:
    • Read current state
    • Update counters
    • Add sources
    • Add thoughts
```

## Configuration Hierarchy

```
1. Default values (in code)
        ↓
2. config.env file
        ↓
3. Environment variables
        ↓
4. Command-line arguments
        ↓
5. Function parameters (highest priority)

Example:
    Default: max_iterations=10
    .env: MAX_ITERATIONS=12
    CLI: --max-iterations 15  ← This wins
```

## Tool Execution Flow

```
1. Agent receives question
        ↓
2. Agent decides to call tool: web_search("quantum computing")
        ↓
3. Tool function executes:
    a. Print status: "🔍 Searching web: quantum computing"
    b. Call DuckDuckGo API
    c. Update iteration count
    d. Return formatted results
        ↓
4. LLM receives tool results
        ↓
5. LLM decides next action:
    • Call another tool? → Go to step 2
    • Provide final answer? → Go to step 6
        ↓
6. Generate structured FinalAnswer
        ↓
7. Return to user
```
