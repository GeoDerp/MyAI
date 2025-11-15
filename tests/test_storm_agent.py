"""
Tests for the STORM research agent.
"""
import unittest
from unittest.mock import MagicMock

from myai.storm_agent import StormAgent, ResearchState
from myai.llm_manager import LLMManager
from myai.runtime_limits import RuntimeLimitExceeded

class TestStormAgent(unittest.TestCase):
    """
    Unit tests for the StormAgent.
    """

    def setUp(self):
        """
        Set up the test environment.
        """
        # Mock the LLMManager
        self.mock_llm_manager = MagicMock(spec=LLMManager)
        
        # Mock the tools
        self.mock_tools = [MagicMock(), MagicMock()]

        # Create the agent
        self.agent = StormAgent(self.mock_llm_manager, self.mock_tools)

    def test_plan_step(self):
        """
        Tests the plan step of the agent.
        """
        # Mock the LLM response
        self.mock_llm_manager.get_completion.return_value = {
            "choices": [{"message": {"content": "{'plan': 'Test plan', 'questions': ['Q1', 'Q2']}"}}]
        }

        initial_state = ResearchState(topic="Test Topic")
        result_state = self.agent._plan_step(initial_state)

        self.assertEqual(result_state.research_plan, "Test plan")
        self.assertEqual(result_state.questions, ["Q1", "Q2"])

    def test_gather_step(self):
        """
        Tests the gather step of the agent.
        """
        # For this test, we'll replace the tool calls with mocks
        with unittest.mock.patch("myai.storm_agent.exa_search_tool") as mock_exa, \
             unittest.mock.patch("myai.storm_agent.arxiv_search_tool") as mock_arxiv:
            
            mock_exa.invoke.return_value = [{"title": "Exa Article"}]
            mock_arxiv.invoke.return_value = [{"title": "Arxiv Article"}]

            initial_state = ResearchState(topic="Test Topic", questions=["Q1"])
            result_state = self.agent._gather_step(initial_state)

            self.assertEqual(len(result_state.articles), 2)
            self.assertEqual(result_state.articles[0]["title"], "Exa Article")
            self.assertEqual(result_state.articles[1]["title"], "Arxiv Article")

    def test_synthesize_step(self):
        """
        Tests the synthesize step of the agent.
        """
        # Mock the LLM response
        self.mock_llm_manager.get_completion.return_value = {
            "choices": [{"message": {"content": "Test report"}}]
        }

        initial_state = ResearchState(topic="Test Topic", articles=[{"text": "Article content"}])
        result_state = self.agent._synthesize_step(initial_state)

        self.assertEqual(result_state.report, "Test report")

    def test_reflect_step(self):
        """
        Tests the reflect step of the agent.
        """
        # Mock the LLM response
        self.mock_llm_manager.get_completion.return_value = {
            "choices": [{"message": {"content": "Feedback: continue"}}]
        }

        initial_state = ResearchState(topic="Test Topic", report="Test report")
        result_state = self.agent._reflect_step(initial_state)

        self.assertEqual(result_state.feedback, "Feedback: continue")
        self.assertIn("continue", result_state.feedback.lower())

    def test_decide_next_step(self):
        """
        Tests the decision logic of the agent.
        """
        state_continue = ResearchState(topic="Test", feedback="Please continue.")
        self.assertEqual(self.agent._decide_next_step(state_continue), "continue")

        state_end = ResearchState(topic="Test", feedback="Looks good.")
        self.assertEqual(self.agent._decide_next_step(state_end), "end")

    def test_runtime_limit_abort(self):
        """Ensure runtime guard aborts and returns partial payload."""
        timeout_exc = RuntimeLimitExceeded(max_seconds=1, elapsed=2.0, step="plan")
        timeout_exc.state_snapshot = ResearchState(topic="Timeout Topic")
        with unittest.mock.patch("myai.storm_agent.RuntimeGuard") as mock_guard:
            guard_instance = unittest.mock.MagicMock()
            guard_instance.ensure_within_budget.side_effect = timeout_exc
            guard_instance.max_seconds = 1
            mock_guard.return_value = guard_instance

            result = self.agent.run("Timeout Topic")

        self.assertTrue(result.get("runtime_limited"))
        self.assertIn("Aborted", result.get("report", ""))

if __name__ == "__main__":
    unittest.main()
