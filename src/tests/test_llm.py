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


def test_format_result_limits_rows():
    rows = [(i, None) for i in range(5)]

    row_info, text = llm.format_result(["id", "name"], rows, max_rows=2)

    assert row_info == "first 2 of 5 rows"
    assert text == "id | name\n0 | NULL\n1 | NULL"


def test_format_result_empty():
    row_info, text = llm.format_result(["id"], [], max_rows=2)

    assert row_info == "0 rows"
    assert text == "id"


def test_generate_answer_prompt(monkeypatch):
    sent = {}

    class Response:
        class message:
            content = "  A válasz 42.\n"
        prompt_eval_count = 3
        eval_count = 2

    def fake_chat(model, messages, options):
        sent["messages"] = messages
        return Response

    monkeypatch.setattr(llm, "chat", fake_chat)

    answer = llm.generate_answer(
        "Hány rendelés van?", "SELECT count(*) AS n FROM orders",
        ["n"], [(42,)], 50, llm.LLMSettings(),
    )

    prompt = sent["messages"][0]["content"]
    assert len(sent["messages"]) == 1
    assert "Hány rendelés van?" in prompt
    assert "SELECT count(*) AS n FROM orders" in prompt
    assert "(1 row)" in prompt
    assert "n\n42" in prompt
    assert answer == llm.Answer(text="A válasz 42.", prompt_tokens=3, completion_tokens=2)