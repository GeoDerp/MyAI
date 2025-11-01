"""
FastAPI application to serve the STORM research agent.
"""
from fastapi import FastAPI
from pydantic import BaseModel
from myai.storm_agent import StormAgent
from myai.llm_manager import LLMManager
from myai.tools import exa_search_tool, arxiv_search_tool, llama_parse_tool
import os
import logging
from fastapi.responses import JSONResponse

logger = logging.getLogger("myai.api")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s'))
    logger.addHandler(h)
    logger.setLevel(os.environ.get('MYAI_LOG_LEVEL', 'INFO'))

# Set API keys as environment variables for the current process
os.environ["LLAMA_CLOUD_API_KEY"] = os.environ.get("LLAMA_CLOUD_API_KEY", "")
os.environ["EXA_API_KEY"] = os.environ.get("EXA_API_KEY", "")

app = FastAPI(
    title="Deep Research Agent API",
    description="An API for running the STORM research agent.",
    version="0.1.0",
)

# --- Initialize Agent ---

# Initialize LLM manager with a sensible default; runtime base_url can be
# overridden by calling test_research_endpoint with base_url or by setting
# the LITELLM_BASE_URL environment variable.
llm_manager = LLMManager(model="gpt-4o", base_url=os.environ.get("LITELLM_BASE_URL", "http://localhost:8080"), api_key=os.environ.get("LITELLM_API_KEY", "sk-no-key-required"))
logger.info("LLMManager initialized with base_url: %s", llm_manager.base_url)
tools = [exa_search_tool, arxiv_search_tool, llama_parse_tool]
agent = StormAgent(llm_manager, tools)

# --- API Models ---

class ResearchRequest(BaseModel):
    topic: str


class ResearchResponse(BaseModel):
    research_plan: str | None = None
    questions: list[str] | None = None
    report: str | None = None
    feedback: str | None = None
    articles: list | None = None


@app.get("/healthz")
def healthz():
    return JSONResponse({"status": "ok"}, status_code=200)


@app.get("/readyz")
def readyz():
    # Simple readiness: check that the app is running. Optionally check LLM reachability.
    status = {"status": "ready", "llm_available": llm_manager.available}
    return JSONResponse(status, status_code=200)


@app.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest):
    """
    Starts a research task on a given topic.
    """
    logger.info("/research called for topic=%s", request.topic)
    result = agent.run(request.topic)
    return ResearchResponse(
        research_plan=result.get("research_plan") or result.get("research_plan", None),
        questions=result.get("questions", []) or [],
        report=result.get("report", "No report generated."),
        feedback=result.get("feedback", None),
        articles=result.get("articles", []),
    )


async def test_research_endpoint(topic: str, base_url: str | None = None, progress_callback=None):
    """
    A test function to directly invoke the research endpoint logic.
    Optionally accepts a `base_url` to override the LLM endpoint at runtime
    (useful for the web UI when the user points to a local RamaLama instance).
    
    Args:
        topic: Research topic/question
        base_url: Optional LLM endpoint URL override
        progress_callback: Optional callback function for progress updates
                          Signature: callback(step, status, message, metadata=None)
    """
    debug_file = os.environ.get("MYAI_DEBUG_FILE")

    # Optionally update LLM manager base_url for this run and invoke the
    # agent directly so we return a plain dict the Flask UI can render.
    if base_url:
        logger.info("test_research_endpoint: setting llm base_url to %s", base_url)
        llm_manager.set_base_url(base_url)
        if debug_file:
            try:
                with open(debug_file, "a") as f:
                    f.write(f"test_research_endpoint: set base_url to {base_url}\n")
            except Exception:
                logger.debug("Unable to write base_url change to debug file %s", debug_file)
    else:
        logger.info("test_research_endpoint: no base_url provided; using configured base_url")
        if debug_file:
            try:
                with open(debug_file, "a") as f:
                    f.write("test_research_endpoint: no base_url provided\n")
            except Exception:
                logger.debug("Unable to write to debug file %s", debug_file)

    logger.info("test_research_endpoint: invoking research for topic=%s", topic)
    if debug_file:
        try:
            with open(debug_file, "a") as f:
                f.write(f"test_research_endpoint: invoking research for topic={topic}\n")
        except Exception:
            logger.debug("Unable to write invocation to debug file %s", debug_file)

    # Directly run the agent to obtain the final state (a dict-like object)
    # Pass progress callback if provided
    final_state = agent.run(topic, progress_callback=progress_callback)

    # Normalize the returned final_state into a plain dict with expected fields
    return {
        "research_plan": final_state.get("research_plan") or final_state.get("research_plan", None),
        "questions": final_state.get("questions", []) or [],
        "report": final_state.get("report"),
        "feedback": final_state.get("feedback"),
        "articles": final_state.get("articles", []) or [],
    }


if __name__ == "__main__":
    import asyncio
    logger.info("Running a sample research task...")
    sample_topic = "The impact of AI on scientific research"
    result = asyncio.run(test_research_endpoint(sample_topic))
    print("\n--- Sample Research Report ---")
    print(result.report)
    print("\n--- Articles ---")
    for article in result.articles:
        print(f"- {article.get('title', 'No Title')}: {article.get('url', 'No URL')}")
