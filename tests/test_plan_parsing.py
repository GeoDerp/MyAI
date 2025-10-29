import json
from myai.storm_agent import StormAgent, ResearchState


class DummyLLM:
    def __init__(self, response_text: str):
        self._resp = {
            "choices": [{"message": {"content": response_text}}]
        }

    def get_completion(self, messages):
        return self._resp

    def extract_assistant_text(self, response):
        return response['choices'][0]['message']['content']


def test_plan_parsing_from_code_fence():
    # Model returns a JSON object wrapped in a ```json code fence
    json_obj = {
        "plan": "Test plan",
        "questions": ["Q1", "Q2"]
    }
    wrapped = "```json\n" + json.dumps(json_obj) + "\n```"

    llm = DummyLLM(wrapped)
    agent = StormAgent(llm_manager=llm, tools=[], max_iterations=1)

    state = ResearchState(topic="test topic")
    new_state = agent._plan_step(state)

    assert new_state.research_plan == "Test plan"
    assert new_state.questions == ["Q1", "Q2"]
