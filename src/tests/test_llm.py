import pytest

import llm
from llm import extract_sql


@pytest.mark.parametrize(
    "response",
    [
        "SELECT 1;",
        "```sql\nSELECT 1;\n```",
        "```postgresql\nSELECT 1;\n```",
        "```\nSELECT 1;\n```",
        "Here is the query:\n```sql\nSELECT 1;\n```\nIt counts rows.",
    ],
)
def test_extract_sql(response):
    assert extract_sql(response) == "SELECT 1;"


def test_correct_sql_continues_the_conversation(monkeypatch):
    sent = {}

    class Response:
        class message:
            content = "SELECT 2;"
        prompt_eval_count = 1
        eval_count = 1

    def fake_chat(model, messages, options):
        sent["messages"] = messages
        return Response

    monkeypatch.setattr(llm, "chat", fake_chat)

    generation = llm.correct_sql(
        "question", "schema", [("SELECT 1;", "some error")], llm.LLMSettings()
    )

    roles = [m["role"] for m in sent["messages"]]
    assert roles == ["user", "assistant", "user"]
    # The first message is the unchanged baseline prompt.
    assert sent["messages"][0]["content"] == llm.PROMPT_TEMPLATE.format(
        schema="schema", question="question"
    )
    assert "some error" in sent["messages"][2]["content"]
    assert generation.sql == "SELECT 2;"