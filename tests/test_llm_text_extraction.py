from pydantic import BaseModel

from myai._llm_manager_impl import LLMManager


class MessageModel(BaseModel):
    role: str = "assistant"
    content: str


class ChoiceModel(BaseModel):
    message: MessageModel
    finish_reason: str = "stop"
    index: int = 0


class ResponseModel(BaseModel):
    choices: list[ChoiceModel]


def test_extract_from_pydantic_response():
    resp = ResponseModel(choices=[ChoiceModel(message=MessageModel(content="Hello from model"))])
    manager = LLMManager()
    assert manager.extract_assistant_text(resp) == "Hello from model"


def test_extract_from_multi_part_content():
    response = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "Part A. "},
                        {"type": "text", "text": "Part B."},
                    ]
                }
            }
        ]
    }
    manager = LLMManager()
    assert manager.extract_assistant_text(response) == "Part A. Part B."
