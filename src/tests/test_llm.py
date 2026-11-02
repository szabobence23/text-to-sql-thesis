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


def fake_replies(monkeypatch, *replies):
    """chat() returns the replies in order; records every prompt sent."""
    sent = []

    def response(content):
        class Response:
            class message:
                pass
            prompt_eval_count = 3
            eval_count = 2
        Response.message.content = content
        return Response

    queue = list(replies)

    def fake_chat(model, messages, options):
        sent.append(messages)
        return response(queue.pop(0))

    monkeypatch.setattr(llm, "chat", fake_chat)
    return sent


def test_generate_answer_checks_then_answers(monkeypatch):
    sent = fake_replies(monkeypatch, "OK", "  A válasz 42.\n")

    answer = llm.generate_answer(
        "Hány rendelés van?", "SELECT count(*) AS n FROM orders",
        ["n"], [(42,)], 50, llm.LLMSettings(),
    )

    check, prompt = (messages[0]["content"] for messages in sent)
    assert all(len(messages) == 1 for messages in sent)
    # The check sees the question and the result, not the SQL.
    assert "Hány rendelés van?" in check and "n\n42" in check
    assert "SELECT count(*)" not in check
    assert "Hány rendelés van?" in prompt
    assert "SELECT count(*) AS n FROM orders" in prompt
    assert "(1 row)" in prompt
    assert "n\n42" in prompt
    assert "NOTE" not in prompt
    assert answer == llm.Answer(text="A válasz 42.", prompt_tokens=6, completion_tokens=4, doubtful=False)


def test_doubtful_result_is_noted_in_the_answer_prompt(monkeypatch):
    sent = fake_replies(monkeypatch, "DOUBTFUL", "Az eredmény 17 futam vezetőit sorolja fel.")

    answer = llm.generate_answer(
        "Ki nyerte a 2007-es bajnokságot?", "SELECT ...",
        ["name"], [("Räikkönen",), ("Alonso",), ("Hamilton",)], 50, llm.LLMSettings(),
    )

    assert "NOTE: A check found" in sent[1][0]["content"]
    assert answer.doubtful is True


@pytest.mark.parametrize(
    "reply, doubtful",
    [("OK", False), ("DOUBTFUL", True), ("**DOUBTFUL**", True), ("doubtful.", True), ("I cannot tell.", None)],
)
def test_check_verdict(reply, doubtful):
    assert llm.check_verdict(reply) == doubtful


def test_sql_prompt_is_unchanged_without_examples():
    assert llm.sql_prompt("q", "schema") == llm.PROMPT_TEMPLATE.format(schema="schema", question="q")


def test_sql_examples_come_right_before_the_question():
    examples = "Question: x\nSQL: SELECT 1;"
    prompt = llm.sql_prompt("q", "schema", examples)

    assert prompt.index("schema") < prompt.index("Question: x") < prompt.index("USER QUESTION:")
    block = llm.SQL_EXAMPLES_BLOCK.format(examples=examples)
    assert prompt.replace(block, "") == llm.sql_prompt("q", "schema")
