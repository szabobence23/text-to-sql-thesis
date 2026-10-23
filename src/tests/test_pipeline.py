import psycopg
import pytest

import pipeline
from dataset_loader import load_dataset
from llm import Answer, Generation, TableSelection, Translation
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
    assert config["schema_retrieval"] == "full"
    assert config["llm"]["temperature"] == 0.0


def test_unknown_schema_retrieval_is_rejected():
    with pytest.raises(ValueError, match="Available"):
        PipelineConfig(schema_retrieval="magic")


@pytest.mark.db
def test_schema_can_be_limited_to_some_tables(conn):
    config = PipelineConfig(dataset="olist")
    schema = load_schema(conn, config, tables={("public", "orders"), ("public", "customers")})

    tables = [line for line in schema.splitlines() if line.startswith("Table: ")]
    assert tables == ["Table: customers", "Table: orders"]
    # Only relationships between two listed tables are kept.
    assert "- orders.customer_id -> customers.customer_id" in schema
    assert "order_items" not in schema
    # Hints are kept: they are not per-table.
    assert load_dataset("olist").hints in schema


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

class FakeRetriever:
    def __init__(self, tables):
        self.tables = tables
        self.queries = []

    def select(self, question):
        self.queries.append(question)
        return self.tables


def test_retrieval_builds_the_schema_from_selected_tables(monkeypatch):
    FakeBackend(monkeypatch, ["good"], {"good": "ok"})
    built = []
    monkeypatch.setattr(
        pipeline, "load_schema",
        lambda conn, config, tables=None: built.append(tables) or "small schema",
    )
    retriever = FakeRetriever([("public", "orders")])

    result = run_pipeline(None, "question", "full schema", PipelineConfig(schema_retrieval="dense"), retriever)

    assert retriever.queries == ["question"]
    assert built == [[("public", "orders")]]
    assert result.schema_tables == [("public", "orders")]
    assert result.retrieval_query == "question"
    assert "retrieval_s" in result.timings


def test_translation_is_used_only_for_retrieval(monkeypatch):
    backend = FakeBackend(monkeypatch, ["good"], {"good": "ok"})
    monkeypatch.setattr(pipeline, "load_schema", lambda conn, config, tables=None: "small schema")
    monkeypatch.setattr(
        pipeline, "translate_question",
        lambda question, settings: Translation("english question", 3, 2),
    )
    seen = []
    monkeypatch.setattr(
        pipeline, "generate_sql",
        lambda question, schema, settings: seen.append((question, schema)) or backend._next(),
    )
    retriever = FakeRetriever([("public", "orders")])

    config = PipelineConfig(schema_retrieval="hybrid", translate_for_retrieval=True)
    result = run_pipeline(None, "magyar kérdés", "full schema", config, retriever)

    assert retriever.queries == ["english question"]
    # The SQL model gets the original question and the retrieved schema.
    assert seen == [("magyar kérdés", "small schema")]
    assert result.translation.text == "english question"
    assert "translation_s" in result.timings


def test_retrieval_mode_without_retriever_is_rejected(monkeypatch):
    FakeBackend(monkeypatch, ["good"], {"good": "ok"})

    with pytest.raises(ValueError, match="needs a retriever"):
        run(PipelineConfig(schema_retrieval="bm25"))


def test_full_schema_records_no_retrieval(monkeypatch):
    FakeBackend(monkeypatch, ["good"], {"good": "ok"})

    result = run(PipelineConfig())

    assert result.schema_tables is None
    assert result.retrieval_query is None


@pytest.mark.db
def test_column_values_list_categories(conn):
    with_values = load_schema(conn, PipelineConfig(dataset="olist", column_values=True))
    without = load_schema(conn, PipelineConfig(dataset="olist"))

    assert "- order_status character varying (values: 'approved', 'canceled'," in with_values
    assert "- payment_type character varying (values: 'boleto', 'credit_card'," in with_values
    # Identifiers and other high-cardinality columns are not listed.
    assert "- customer_id character varying\n" in with_values
    assert "values:" not in without


class FakeSelectingRetriever(FakeRetriever):
    def describe(self, keys):
        return "tables"

    def expand(self, keys):
        return list(keys) + [("public", "bridge")]


def test_table_selection_keeps_chosen_tables_plus_bridges(monkeypatch):
    FakeBackend(monkeypatch, ["good"], {"good": "ok"})
    monkeypatch.setattr(pipeline, "load_schema", lambda conn, config, tables=None: "small schema")
    monkeypatch.setattr(pipeline, "choose_tables", lambda q, t, s, style: TableSelection("orders", 4, 1))
    retriever = FakeSelectingRetriever([("public", "orders"), ("public", "sellers")])

    config = PipelineConfig(schema_retrieval="dense", table_selection=True)
    result = run_pipeline(None, "question", "full schema", config, retriever)

    assert result.candidate_tables == [("public", "orders"), ("public", "sellers")]
    assert result.schema_tables == [("public", "orders"), ("public", "bridge")]
    assert "selection_s" in result.timings


def test_table_selection_naming_nothing_keeps_all_candidates(monkeypatch):
    FakeBackend(monkeypatch, ["good"], {"good": "ok"})
    monkeypatch.setattr(pipeline, "load_schema", lambda conn, config, tables=None: "small schema")
    monkeypatch.setattr(pipeline, "choose_tables", lambda q, t, s, style: TableSelection("I am not sure.", 4, 1))
    retriever = FakeSelectingRetriever([("public", "orders"), ("public", "sellers")])

    config = PipelineConfig(schema_retrieval="dense", table_selection=True)
    result = run_pipeline(None, "question", "full schema", config, retriever)

    assert result.schema_tables == [("public", "orders"), ("public", "sellers")]


def test_table_selection_needs_retrieval():
    with pytest.raises(ValueError, match="filters retrieved tables"):
        PipelineConfig(table_selection=True)


def test_selection_keep_top_adds_back_top_candidates(monkeypatch):
    FakeBackend(monkeypatch, ["good"], {"good": "ok"})
    monkeypatch.setattr(pipeline, "load_schema", lambda conn, config, tables=None: "small schema")
    styles = []
    monkeypatch.setattr(
        pipeline, "choose_tables",
        lambda q, t, s, style: styles.append(style) or TableSelection("sellers", 4, 1),
    )
    retriever = FakeSelectingRetriever([("public", "orders"), ("public", "items"), ("public", "sellers")])

    config = PipelineConfig(
        schema_retrieval="dense", table_selection=True,
        table_selection_style="inclusive", selection_keep_top=2,
    )
    result = run_pipeline(None, "question", "full schema", config, retriever)

    assert styles == ["inclusive"]
    # The model's choice first, then the top-2 candidates, then bridges.
    assert result.schema_tables == [
        ("public", "sellers"), ("public", "orders"), ("public", "items"), ("public", "bridge"),
    ]


def test_unknown_selection_style_is_rejected():
    with pytest.raises(ValueError, match="table_selection_style"):
        PipelineConfig(schema_retrieval="dense", table_selection=True, table_selection_style="loose")
