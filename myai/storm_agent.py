"""
Core logic for the STORM research agent using LangGraph.
"""
from typing import List, Dict, Any, Optional, Callable
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
import os
import json

from myai.llm_manager import LLMManager
from myai.tools import (
    exa_search_tool,
    arxiv_search_tool,
    llama_parse_tool,
    pubmed_search_tool,
)
from myai.adaptive_llm import AdaptiveLLMHandler
from myai.runtime_limits import RuntimeGuard, RuntimeLimitExceeded, resolve_runtime_limit_seconds

# --- Agent State ---

class ResearchState(BaseModel):
    """
    Represents the state of the research process.
    """
    topic: str = Field(description="The main topic of the research.")
    research_plan: Optional[str] = Field(None, description="The plan for conducting the research.")
    questions: List[str] = Field(default_factory=list, description="A list of questions to research.")
    articles: List[Dict[str, Any]] = Field(default_factory=list, description="A list of gathered articles and their content.")
    report: Optional[str] = Field(None, description="The final research report.")
    feedback: Optional[str] = Field(None, description="Feedback on the report from the user or a critic agent.")

# --- Agent Nodes ---

class StormAgent:
    """
    An agent that implements the STORM research methodology using LangGraph.
    """

    def __init__(self, llm_manager: LLMManager, tools: List[Any], max_iterations: int = 5, max_runtime_seconds: int | None = None):
        self.llm_manager = llm_manager
        self.tools = tools
        self.exa_api_key = os.environ.get("EXA_API_KEY")
        self.llama_cloud_api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
        
        # Auto-reduce max_iterations for CPU-only mode to prevent excessive runtime
        cpu_only = self._detect_cpu_only_mode()
        if cpu_only and max_iterations > 2:
            print(f"[StormAgent] CPU-only mode detected. Reducing max_iterations from {max_iterations} to 2 to limit runtime.")
            max_iterations = 2
        
        self.max_iterations = max_iterations
        # internal counter to avoid infinite loops in LangGraph
        self._iteration = 0
        
        # Progress callback for real-time updates
        self.progress_callback = None

        # Runtime guard configuration (default 30 minutes)
        self.max_runtime_seconds = resolve_runtime_limit_seconds(max_runtime_seconds)
        self._runtime_guard: RuntimeGuard | None = None
        
        # Initialize adaptive LLM handler for slow models
        self.adaptive_handler = AdaptiveLLMHandler(
            llm_manager=llm_manager,
            base_timeout=int(os.environ.get("LLM_BASE_TIMEOUT", "90")),
            max_timeout=int(os.environ.get("LLM_MAX_TIMEOUT", "300")),
            min_timeout=int(os.environ.get("LLM_MIN_TIMEOUT", "30"))
        )
        
        self.graph = self._build_graph()
    
    def _ensure_runtime_budget(self, state: ResearchState | None, step: str) -> None:
        if not self._runtime_guard:
            return
        try:
            self._runtime_guard.ensure_within_budget(step)
        except RuntimeLimitExceeded as exc:
            if state is not None:
                try:
                    exc.state_snapshot = state.model_copy(deep=True)
                except Exception:
                    exc.state_snapshot = state
            raise

    def _report_progress(self, step, status, message, metadata=None):
        """Helper to report progress if callback is set"""
        if self.progress_callback:
            try:
                self.progress_callback(step, status, message, metadata)
            except Exception as e:
                print(f"[StormAgent] Progress callback error: {e}")
    
    def _detect_cpu_only_mode(self) -> bool:
        """
        Detect if running in CPU-only mode based on environment variables.
        Returns True if CPU-only, False otherwise.
        """
        if os.environ.get("CPU_ONLY_MODE", "").lower() in ("1", "true", "yes"):
            return True
        if os.environ.get("GPU_LAYERS", "") == "0":
            return True
        vram_mb = os.environ.get("GPU_VRAM_MB", "")
        if vram_mb and vram_mb.isdigit() and int(vram_mb) < 1024:
            return True
        return False

    def _build_graph(self) -> StateGraph:
        """
        Builds the LangGraph for the research process.
        """
        graph = StateGraph(ResearchState)

        # Add nodes
        graph.add_node("plan", self._plan_step)
        graph.add_node("gather", self._gather_step)
        graph.add_node("synthesize", self._synthesize_step)
        graph.add_node("reflect", self._reflect_step)

        # Add edges
        graph.set_entry_point("plan")
        graph.add_edge("plan", "gather")
        graph.add_edge("gather", "synthesize")
        graph.add_edge("synthesize", "reflect")
        graph.add_conditional_edges(
            "reflect",
            self._decide_next_step,
            {"continue": "gather", "end": END},
        )

        return graph.compile()

    def _plan_step(self, state: ResearchState) -> ResearchState:
        """
        Generates a research plan and a list of questions to investigate.
        Uses adaptive timeout for slow models.
        """
        self._ensure_runtime_budget(state, "plan")
        print("--- Plan Step ---")
        self._report_progress("plan", "starting", "Generating research plan...")
        
        messages = [
            {"role": "user", "content": f"Generate a concise research plan and a list of specific questions for the topic: {state.topic}. Your response MUST be a valid JSON object with two keys: \"plan\" (string, a brief overview of the research approach) and \"questions\" (list of strings, specific questions to investigate). Example: {{ \"plan\": \"Overview of AI impact\", \"questions\": [\"What is AI?\", \"How does AI affect research?\"] }}"}
        ]
        # Debug: show that we're about to call the LLM
        try:
            availability = getattr(self.llm_manager, "available", None)
            base = getattr(self.llm_manager, "base_url", None)
            msg = f"[DEBUG] StormAgent._plan_step: calling adaptive handler (base_url={base}, available={availability}, messages_len={len(messages)})\n"
            print(msg.strip())
            try:
                with open("/tmp/myai_debug.log", "a") as f:
                    f.write(msg)
            except Exception:
                pass
        except Exception:
            print("[DEBUG] StormAgent._plan_step: calling adaptive handler")

        self._report_progress("plan", "running", "Waiting for LLM response...")
        
        # Use adaptive handler with shorter timeout for plan generation
        response = self.adaptive_handler.get_completion_adaptive(messages, fallback_on_timeout=True)
        try:
            # Use LLMManager helper to extract assistant text in a normalized form.
            result_content = self.llm_manager.extract_assistant_text(response)
            # Tests may provide MagicMock or non-str values; only treat real strings
            # as valid normalized content. Otherwise fall back to the raw response
            # structure so tests that mock get_completion still work.
            if not isinstance(result_content, str):
                choices = (response or {}).get("choices")
                if choices and choices[0].get("message") and choices[0]["message"].get("content"):
                    result_content = choices[0]["message"]["content"]
                else:
                    result_content = None

            if not isinstance(result_content, str):
                raise ValueError("No string assistant content available")

            self._report_progress("plan", "running", "Parsing plan response...")
            
            # Pre-process the assistant text to remove common wrappers such as
            # Markdown code fences (```json ... ```), triple backticks, or
            # surrounding explanation text that causes json.loads to fail.
            try:
                import re
                cleaned = result_content.strip()
                # If the model wrapped JSON in a fenced code block, extract it
                m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
                if m:
                    cleaned = m.group(1).strip()

                # Also try to extract the first {...} block if present
                m2 = re.search(r"(\{[\s\S]*\})", cleaned)
                if m2:
                    cleaned = m2.group(1)

                # If it looks like JSON, parse it
                try:
                    plan_data = json.loads(cleaned)
                except json.JSONDecodeError:
                    # Some LLMs return Python-style dicts with single quotes;
                    # try a safe Python literal evaluation as a fallback.
                    import ast
                    plan_data = ast.literal_eval(cleaned)
            except Exception as ex:
                # Surface the underlying exception to be handled by the outer
                # except block below which sets default plan/questions.
                raise

            state.research_plan = plan_data.get("plan")
            state.questions = plan_data.get("questions", [])
            
            num_questions = len(state.questions)
            self._report_progress("plan", "completed", 
                                f"Plan generated with {num_questions} research questions",
                                {"num_questions": num_questions})
        except Exception as e:
            print(f"Error parsing plan from LLM: {e}")
            # Try to present a useful normalized dump for debugging
            try:
                raw_norm = self.llm_manager.extract_assistant_text(response)
            except Exception:
                raw_norm = None
            print(f"Raw LLM response (normalized): {raw_norm}")
            state.research_plan = "Default plan: Gather articles and synthesize a report."
            state.questions = [f"What is {state.topic}?", f"What are the key aspects of {state.topic}?"]
            
            self._report_progress("plan", "completed", 
                                "Using default plan (LLM parse failed)",
                                {"num_questions": len(state.questions)})
        
        return state

    def _gather_step(self, state: ResearchState) -> ResearchState:
        """
        Gathers articles and information based on the research questions.
        """
        self._ensure_runtime_budget(state, "gather")
        print("--- Gather Step ---")
        self._report_progress("gather", "starting", 
                            f"Searching for articles ({len(state.questions)} questions)...")
        
        total_questions = len(state.questions)

        def _parse_cap(val):
            if not val:
                return None
            try:
                parsed = int(val)
                return parsed if parsed > 0 else None
            except (ValueError, TypeError):
                return None

        default_cap = _parse_cap(os.environ.get("MYAI_MAX_ARTICLES")) or 40
        cpu_cap = _parse_cap(os.environ.get("MYAI_CPU_MAX_ARTICLES")) or 18
        article_cap = default_cap
        if self.adaptive_handler.cpu_only_mode and cpu_cap:
            article_cap = min(article_cap, cpu_cap)
        for idx, question in enumerate(state.questions, 1):
            self._ensure_runtime_budget(state, f"gather-q{idx}")
            print(f"Searching for: {question}")
            self._report_progress("gather", "running", 
                                f"Question {idx}/{total_questions}: {question[:50]}...",
                                {"current_question": idx, "total_questions": total_questions})
            
            # Use Exa and Arxiv tools to search for articles, passing API key to Exa
            exa_results = exa_search_tool.invoke({"query": question, "api_key": os.environ.get("EXA_API_KEY")})
            arxiv_results = arxiv_search_tool.invoke(question)
            
            print(f"[DEBUG] About to call PubMed with query: {question}")
            pubmed_results = pubmed_search_tool.invoke({"query": question, "max_results": 5})
            print(f"[DEBUG] PubMed returned {len(pubmed_results)} results")
            if pubmed_results:
                print(f"[DEBUG] First PubMed result: {pubmed_results[0].get('title', 'NO TITLE')[:80]}")
            
            # Log results from each source
            print(f"[Gather] Question {idx}: PubMed={len(pubmed_results)}, Exa={len(exa_results)}, ArXiv={len(arxiv_results)}")
            
            state.articles.extend(pubmed_results)
            state.articles.extend(exa_results)
            state.articles.extend(arxiv_results)
        
        num_articles = len(state.articles)
        trimmed_from = None
        if article_cap and num_articles > article_cap:
            trimmed_from = num_articles
            state.articles = state.articles[:article_cap]
            num_articles = article_cap
            print(
                f"[INFO] CPU-friendly article cap applied: trimmed {trimmed_from} -> {num_articles} (cpu_only={self.adaptive_handler.cpu_only_mode})"
            )

        status_msg = f"Gathered {num_articles} articles"
        if trimmed_from:
            status_msg += " (capped for CPU mode)"

        self._report_progress("gather", "completed", 
                        status_msg,
                        {"num_articles": num_articles, "trimmed_from": trimmed_from})
        
        # Example of using LlamaParse (you would typically have a separate step for this)
        # For demonstration, let's assume we have a PDF file to parse.
        # In a real scenario, you'd download PDFs from search results and then parse them.
        # if os.environ.get("LLAMA_CLOUD_API_KEY") and os.path.exists("example.pdf"): # You'd replace "example.pdf" with actual downloaded file paths
        #     print("Parsing PDF with LlamaParse...")
        #     parsed_docs = llama_parse_tool.invoke({"file_path": "example.pdf", "api_key": os.environ.get("LLAMA_CLOUD_API_KEY")})
        #     state.articles.extend(parsed_docs)
        
        return state

    def _synthesize_step(self, state: ResearchState) -> ResearchState:
        """
        Synthesizes the gathered information into a research report.
        Uses adaptive strategies for slow or limited LLMs.
        """
        self._ensure_runtime_budget(state, "synthesize")
        print("--- Synthesize Step ---")
        self._report_progress("synthesize", "starting", 
                            f"Synthesizing report from {len(state.articles)} articles...")
        
        # Check if we should use chunked processing
        total_chars = sum(len(article.get("text", "") or article.get("summary", "")) for article in state.articles)
        # Use higher threshold to reduce chunking frequency (fewer LLM calls)
        use_chunking = total_chars > 20000 or len(state.articles) > 12
        
        if use_chunking:
            print(f"[INFO] Using chunked synthesis for {len(state.articles)} articles ({total_chars} chars)")
            self._report_progress("synthesize", "running", 
                                f"Processing {total_chars} chars in chunks...",
                                {"total_chars": total_chars, "chunked": True})
            try:
                state.report = self.adaptive_handler.synthesize_with_chunking(
                    topic=state.topic,
                    articles=state.articles,
                    max_chunk_chars=8000
                )
                self._report_progress("synthesize", "completed", 
                                    "Report synthesis complete")
                return state
            except Exception as e:
                print(f"[WARN] Chunked synthesis failed: {e}, falling back to standard method")
                self._report_progress("synthesize", "running", 
                                    "Chunked synthesis failed, using standard method...")
        
        # Standard synthesis with adaptive timeout
        self._report_progress("synthesize", "running", 
                            "Generating report with standard synthesis...")
        
        article_texts = "\n\n".join([
            article.get("text", "") or article.get("summary", "") for article in state.articles
        ])

        # Truncate to a reasonable size
        max_chars = 15000
        truncated = False
        if len(article_texts) > max_chars:
            article_texts = article_texts[:max_chars]
            truncated = True

        prompt = f"Based on the following articles, write a research report on the topic: {state.topic}\n\nArticles:\n{article_texts}"
        if truncated:
            prompt += "\n\n[NOTE: Article text was truncated due to length limits]"

        messages = [{"role": "user", "content": prompt}]

        # Debug: notify before calling the LLM for synthesis
        try:
            availability = getattr(self.llm_manager, "available", None)
            base = getattr(self.llm_manager, "base_url", None)
            msg = f"[DEBUG] StormAgent._synthesize_step: calling adaptive handler (base_url={base}, available={availability}, prompt_len={len(prompt)})\n"
            print(msg.strip())
            try:
                with open("/tmp/myai_debug.log", "a") as f:
                    f.write(msg)
            except Exception:
                pass
        except Exception:
            print("[DEBUG] StormAgent._synthesize_step: calling adaptive handler")

        # Use adaptive handler instead of direct LLM call
        response = self.adaptive_handler.get_completion_adaptive(
            messages, 
            fallback_on_timeout=True,
            enable_chunking=use_chunking
        )

        # Handle cases where the LLM call failed or returned None
        if not response:
            print("[WARN _synthesize_step] Adaptive handler returned no response; setting fallback report.")
            state.report = "[Report generation failed: LLM did not return a response after adaptive retries. Please try again with fewer articles or configure a faster model.]"
            self._report_progress("synthesize", "failed", "Report generation failed")
            return state

        # Safely extract the assistant message content
        try:
            # Prefer normalized assistant content
            assistant_text = self.llm_manager.extract_assistant_text(response)
            # Ensure the extracted content is an actual string (tests may provide MagicMock)
            if isinstance(assistant_text, str) and assistant_text:
                state.report = assistant_text
            else:
                # Fallback to raw structure
                choices = (response or {}).get("choices")
                if choices and choices[0].get("message") and choices[0]["message"].get("content"):
                    state.report = choices[0]["message"]["content"]
                else:
                    raise ValueError("Malformed LLM response: missing content")
            
            self._report_progress("synthesize", "completed", 
                                f"Report generated ({len(state.report)} chars)")
        except Exception as e:
            print(f"[ERROR _synthesize_step] Failed to extract report from LLM response: {e}")
            print(f"Raw LLM response: {response}")
            state.report = "[Report generation failed: unable to parse LLM response. See logs for raw output.]"
            self._report_progress("synthesize", "failed", f"Parse error: {str(e)}")

        return state

    def _reflect_step(self, state: ResearchState) -> ResearchState:
        """
        Reflects on the generated report and decides whether to continue.
        """
        self._ensure_runtime_budget(state, "reflect")
        print("--- Reflect Step ---")
        self._report_progress("reflect", "starting", 
                            f"Reviewing report (iteration {self._iteration + 1}/{self.max_iterations})...")
        
        messages = [
            {"role": "user", "content": f"Review the following report on {state.topic} and provide feedback. Should the research continue? Report:\n{state.report}"}
        ]
        # Debug: notify before calling the LLM for reflection
        try:
            availability = getattr(self.llm_manager, "available", None)
            base = getattr(self.llm_manager, "base_url", None)
            msg = f"[DEBUG] StormAgent._reflect_step: calling llm_manager.get_completion (base_url={base}, available={availability}, report_len={len(state.report or '')})\n"
            print(msg.strip())
            try:
                with open("/tmp/myai_debug.log", "a") as f:
                    f.write(msg)
            except Exception:
                pass
        except Exception:
            print("[DEBUG] StormAgent._reflect_step: calling llm_manager.get_completion (unable to read llm_manager state)")

        response = self.llm_manager.get_completion(messages)
        if not response:
            print("[WARN _reflect_step] LLM returned no response; ending research loop.")
            state.feedback = "No feedback (LLM unavailable)."
            self._report_progress("reflect", "completed", "No feedback (LLM unavailable)")
            return state

        try:
            feedback = self.llm_manager.extract_assistant_text(response)
            # Accept only real string feedback; otherwise fallback to raw response
            if not (isinstance(feedback, str) and feedback):
                choices = (response or {}).get("choices")
                if choices and choices[0].get("message") and choices[0]["message"].get("content"):
                    feedback = choices[0]["message"]["content"]
                else:
                    raise ValueError("No feedback content available")
        except Exception:
            print(f"[WARN _reflect_step] Malformed LLM response: {response}")
            state.feedback = "No feedback (malformed LLM response)."
            self._report_progress("reflect", "completed", "Malformed LLM response")
            return state

        state.feedback = feedback

        # Simple decision logic for now
        if "continue" in feedback.lower():
            # In a real implementation, you would update the questions and plan based on the feedback.
            state.questions = [f"What are the missing aspects in the report on {state.topic}?"]
            self._report_progress("reflect", "completed", "Continuing research (iteration complete)")
        else:
            self._report_progress("reflect", "completed", "Research complete (satisfied)")

        # increment iteration counter and enforce max iterations
        self._iteration += 1
        if self._iteration >= self.max_iterations:
            print(f"[INFO] Reached max_iterations ({self.max_iterations}); ending research loop.")
            # Clear feedback so _decide_next_step will return 'end'
            state.feedback = (state.feedback or "") + " (max iterations reached)"
            self._report_progress("reflect", "completed", f"Max iterations ({self.max_iterations}) reached")

        return state

    def _decide_next_step(self, state: ResearchState) -> str:
        """
        Decides whether to continue the research or end the process.
        """
        # If we've reached the max iterations, force an end to the research loop
        if getattr(self, "_iteration", 0) >= getattr(self, "max_iterations", 0):
            return "end"

        if "continue" in (state.feedback or "").lower():
            return "continue"
        return "end"

    def run(self, topic: str, progress_callback=None) -> Dict[str, Any]:
        """
        Runs the research agent on a given topic.
        
        Args:
            topic: Research topic/question
            progress_callback: Optional callback for progress updates
                             Signature: callback(step, status, message, metadata=None)
        """
        # Set progress callback for this run
        self.progress_callback = progress_callback
        # reset iteration counter each run
        self._iteration = 0
        initial_state = ResearchState(topic=topic)
        self._runtime_guard = RuntimeGuard(self.max_runtime_seconds)
        try:
            final_state = self.graph.invoke(initial_state)
            return final_state
        except RuntimeLimitExceeded as exc:
            self._report_progress(
                "runtime",
                "failed",
                str(exc),
                {
                    "elapsed_seconds": round(exc.elapsed, 2),
                    "max_seconds": exc.max_seconds,
                },
            )
            snapshot = exc.state_snapshot or initial_state
            if isinstance(snapshot, ResearchState):
                payload = snapshot.model_dump()
            else:
                payload = dict(snapshot)
            payload.setdefault("questions", [])
            payload.setdefault("articles", [])
            payload["report"] = payload.get("report") or (
                f"[Aborted: runtime limit {exc.max_seconds}s exceeded after {exc.elapsed:.2f}s]"
            )
            payload["feedback"] = (
                payload.get("feedback")
                or "Runtime limit exceeded; partial results only."
            )
            payload["runtime_limited"] = True
            payload["runtime_elapsed_seconds"] = round(exc.elapsed, 2)
            return payload
        finally:
            self._runtime_guard = None

# Example usage:
if __name__ == "__main__":
    llm_manager = LLMManager(model="ollama/llama3")
    tools = [exa_search_tool, arxiv_search_tool, llama_parse_tool]
    
    agent = StormAgent(llm_manager, tools)
    
    # Note: This requires API keys for Exa and LlamaParse to be set.
    # It also requires an Ollama server to be running with the llama3 model.
    try:
        result = agent.run("The impact of AI on scientific research")
        print("\n--- Final Report ---")
        print(result.get("report"))
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure that Ollama is running, and you have set the required API keys.")

