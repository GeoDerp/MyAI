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
from myai.tools import exa_search_tool, arxiv_search_tool, llama_parse_tool

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

    def __init__(self, llm_manager: LLMManager, tools: List[Any], max_iterations: int = 5):
        self.llm_manager = llm_manager
        self.tools = tools
        self.exa_api_key = os.environ.get("EXA_API_KEY")
        self.llama_cloud_api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
        self.max_iterations = max_iterations
        # internal counter to avoid infinite loops in LangGraph
        self._iteration = 0
        self.graph = self._build_graph()

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
        """
        print("--- Plan Step ---")
        messages = [
            {"role": "user", "content": f"Generate a concise research plan and a list of specific questions for the topic: {state.topic}. Your response MUST be a valid JSON object with two keys: \"plan\" (string, a brief overview of the research approach) and \"questions\" (list of strings, specific questions to investigate). Example: {{ \"plan\": \"Overview of AI impact\", \"questions\": [\"What is AI?\", \"How does AI affect research?\"] }}"}
        ]
        # Debug: show that we're about to call the LLM
        try:
            availability = getattr(self.llm_manager, "available", None)
            base = getattr(self.llm_manager, "base_url", None)
            msg = f"[DEBUG] StormAgent._plan_step: calling llm_manager.get_completion (base_url={base}, available={availability}, messages_len={len(messages)})\n"
            print(msg.strip())
            try:
                with open("/tmp/myai_debug.log", "a") as f:
                    f.write(msg)
            except Exception:
                pass
        except Exception:
            print("[DEBUG] StormAgent._plan_step: calling llm_manager.get_completion (unable to read llm_manager state)")

        response = self.llm_manager.get_completion(messages)
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
        
        return state

    def _gather_step(self, state: ResearchState) -> ResearchState:
        """
        Gathers articles and information based on the research questions.
        """
        print("--- Gather Step ---")
        for question in state.questions:
            print(f"Searching for: {question}")
            # Use Exa and Arxiv tools to search for articles, passing API key to Exa
            exa_results = exa_search_tool.invoke({"query": question, "api_key": os.environ.get("EXA_API_KEY")})
            arxiv_results = arxiv_search_tool.invoke(question)
            
            state.articles.extend(exa_results)
            state.articles.extend(arxiv_results)
        
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
        """
        print("--- Synthesize Step ---")
        # Concatenate article texts but guard against extremely long contexts which can break local LLMs
        article_texts = "\n\n".join([
            article.get("text", "") or article.get("summary", "") for article in state.articles
        ])

        # Truncate to a reasonable size to avoid context-size errors from the LLM backend.
        # Adjust max_chars based on your local model's context window. 20000 is a conservative default.
        max_chars = 20000
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
            msg = f"[DEBUG] StormAgent._synthesize_step: calling llm_manager.get_completion (base_url={base}, available={availability}, prompt_len={len(prompt)})\n"
            print(msg.strip())
            try:
                with open("/tmp/myai_debug.log", "a") as f:
                    f.write(msg)
            except Exception:
                pass
        except Exception:
            print("[DEBUG] StormAgent._synthesize_step: calling llm_manager.get_completion (unable to read llm_manager state)")

        response = self.llm_manager.get_completion(messages)

        # Handle cases where the LLM call failed or returned None
        if not response:
            print("[WARN _synthesize_step] LLM returned no response; setting fallback report.")
            state.report = "[Report generation failed: LLM did not return a response. Please try again with a smaller corpus or configure a larger context window.]"
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
        except Exception as e:
            print(f"[ERROR _synthesize_step] Failed to extract report from LLM response: {e}")
            print(f"Raw LLM response: {response}")
            state.report = "[Report generation failed: unable to parse LLM response. See logs for raw output.]"

        return state

    def _reflect_step(self, state: ResearchState) -> ResearchState:
        """
        Reflects on the generated report and decides whether to continue.
        """
        print("--- Reflect Step ---")
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
            return state

        state.feedback = feedback

        # Simple decision logic for now
        if "continue" in feedback.lower():
            # In a real implementation, you would update the questions and plan based on the feedback.
            state.questions = [f"What are the missing aspects in the report on {state.topic}?"]

        # increment iteration counter and enforce max iterations
        self._iteration += 1
        if self._iteration >= self.max_iterations:
            print(f"[INFO] Reached max_iterations ({self.max_iterations}); ending research loop.")
            # Clear feedback so _decide_next_step will return 'end'
            state.feedback = (state.feedback or "") + " (max iterations reached)"

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

    def run(self, topic: str) -> Dict[str, Any]:
        """
        Runs the research agent on a given topic.
        """
        # reset iteration counter each run
        self._iteration = 0
        initial_state = ResearchState(topic=topic)
        final_state = self.graph.invoke(initial_state)
        return final_state

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

