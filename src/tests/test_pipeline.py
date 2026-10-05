import psycopg
import pytest

import pipeline
from dataset_loader import load_dataset
from llm import Answer, Generation
from pipeline import PipelineConfig, load_schema, open_connection, run_pipeline


@pytest.fixture
def conn():
    connection = open_connection(PipelineConfig(dataset="olist"))

    try:
        yield connection
    finally:
        connection.close()


def test_default_config_is_serializable():
    config = PipelineConfig().to_dict()

    assert config["schema_hints"] is True
    assert config["llm"]["temperature"] == 0.0


@pytest.mark.db
def test_schema_hints_switch(conn):
    hints = load_dataset("olist").hints
    with_hints = load_schema(conn, PipelineConfig(dataset="olist", schema_hints=True))
    without_hints = load_schema(conn, PipelineConfig(dataset="olist", schema_hints=False))

    assert hints.startswith("Important notes:")
    assert with_hints.startswith("Database: olist_db")
    assert hints in with_hints
    assert hints not in without_hints
    # FK relationships must survive the read-only role (pg_catalog query).
    assert "- orders.customer_id -> customers.customer_id" in without_hints


class FakeBackend:
    """
    Stands in for the LLM and the database. Each generated query is
    looked up in `outcomes`: "ok", "invalid" or "exec_error".
    """

    def __init__(self, monkeypatch, generated_sqls, outcomes):
        self.generated = list(generated_sqls)
        self.outcomes = outcomes
        self.correction_calls = []
        self.answer_calls = []

        monkeypatch.setattr(pipeline, "generate_sql", self.generate)
        monkeypatch.setattr(pipeline, "correct_sql", self.correct)
        monkeypatch.setattr(pipeline, "validate_sql", self.validate)
        monkeypatch.setattr(pipeline, "execute_query_with_columns", self.execute)
        monkeypatch.setattr(pipeline, "generate_answer", self.answer)

    def _next(self):
        sql = self.generated.pop(0)
        return Generation(sql=sql, raw_response=sql, prompt_tokens=10, completion_tokens=5)

    def generate(self, question, schema, settings):
        return self._next()

    def correct(self, question, schema, failed_attempts, settings):
        self.correction_calls.append(list(failed_attempts))
        return self._next()

    def validate(self, conn, sql, block_functions=True):
        if self.outcomes[sql] == "invalid":
            return False, f"invalid: {sql}"
        return True, ""

    def execute(self, conn, sql):
        if self.outcomes[sql] == "exec_error":
            raise psycopg.errors.DivisionByZero(f"exec error: {sql}")
        return ["col"], [(sql,)]

    def answer(self, question, sql, columns, rows, max_rows, settings):
        self.answer_calls.append((sql, columns, rows))
        return Answer(text=f"answer from {sql}", prompt_tokens=7, completion_tokens=3)


def run(config):
    return run_pipeline(None, "question", "schema", config)


def test_no_correction_by_default(monkeypatch):
    backend = FakeBackend(monkeypatch, ["bad"], {"bad": "invalid"})

    result = run(PipelineConfig())

    assert not result.executed
    assert result.correction_rounds == 0
    assert backend.correction_calls == []


def test_first_attempt_ok_needs_no_correction(monkeypatch):
    backend = FakeBackend(monkeypatch, ["good"], {"good": "ok"})

    result = run(PipelineConfig(max_correction_rounds=2))

    assert result.executed
    assert result.correction_rounds == 0
    assert backend.correction_calls == []


def test_correction_fixes_invalid_sql(monkeypatch):
    backend = FakeBackend(
        monkeypatch, ["bad", "good"], {"bad": "invalid", "good": "ok"}
    )

    result = run(PipelineConfig(max_correction_rounds=2))

    assert result.executed
    assert result.sql == "good"
    assert result.rows == [("good",)]
    assert result.correction_rounds == 1
    assert backend.correction_calls == [[("bad", "invalid: bad")]]
    # Tokens are totals over both attempts.
    assert result.prompt_tokens == 20


def test_execution_error_triggers_correction(monkeypatch):
    FakeBackend(
        monkeypatch, ["slow", "good"], {"slow": "exec_error", "good": "ok"}
    )

    result = run(PipelineConfig(max_correction_rounds=1))

    assert result.executed
    assert result.attempts[0].is_valid
    assert "exec error" in result.attempts[0].error


def test_stops_after_max_rounds_with_full_history(monkeypatch):
    backend = FakeBackend(
        monkeypatch,
        ["bad1", "bad2", "bad3"],
        {"bad1": "invalid", "bad2": "invalid", "bad3": "invalid"},
    )

    result = run(PipelineConfig(max_correction_rounds=2))

    assert not result.executed
    assert result.sql == "bad3"
    assert result.correction_rounds == 2
    # The second correction sees both earlier failures, oldest first.
    assert backend.correction_calls[1] == [
        ("bad1", "invalid: bad1"),
        ("bad2", "invalid: bad2"),
    ]


def test_no_answer_by_default(monkeypatch):
    backend = FakeBackend(monkeypatch, ["good"], {"good": "ok"})

    result = run(PipelineConfig())

    assert result.answer is None
    assert backend.answer_calls == []
    assert "answer_s" not in result.timings


def test_answer_uses_final_executed_attempt(monkeypatch):
    backend = FakeBackend(
        monkeypatch, ["bad", "good"], {"bad": "invalid", "good": "ok"}
    )

    result = run(PipelineConfig(max_correction_rounds=1, natural_language_answer=True))

    assert result.answer.text == "answer from good"
    assert backend.answer_calls == [("good", ["col"], [("good",)])]
    assert "answer_s" in result.timings
    # Answer tokens are kept apart from the SQL attempts' totals.
    assert result.prompt_tokens == 20


def test_no_answer_when_query_failed(monkeypatch):
    backend = FakeBackend(monkeypatch, ["bad"], {"bad": "invalid"})

    result = run(PipelineConfig(natural_language_answer=True))

    assert result.answer is None
    assert backend.answer_calls == []