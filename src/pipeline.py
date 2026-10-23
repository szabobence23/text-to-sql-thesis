import time
from dataclasses import asdict, dataclass, field

import psycopg

from database import execute_query_with_columns, get_connection
from dataset_loader import DEFAULT_DATASET, load_dataset
from llm import (
    Answer,
    LLMSettings,
    TABLE_SELECTION_TEMPLATES,
    TableSelection,
    Translation,
    choose_tables,
    correct_sql,
    generate_answer,
    generate_sql,
    model_digest,
    translate_question,
)
from retrieval import RETRIEVAL_METHODS, SchemaRetriever, parse_table_choice
from schema import fetch_column_values, get_schema
from sql_validator import validate_sql


SCHEMA_RETRIEVAL_MODES = ("full", "oracle", *RETRIEVAL_METHODS)

# The schema-retrieval configuration chosen from the AdventureWorks
# experiments: multilingual embedding retrieval of 10 candidate tables,
# FK bridges, then strict LLM table selection. The refinements tried on
# top of it (keeping the top-2 candidates, an inclusive selection prompt)
# did not measurably help. `--rag` in the demo and the evaluator applies
# these settings; column values are a separate switch.
RAG_SETTINGS = {
    "schema_retrieval": "dense",
    "retrieval_k": 10,
    "retrieval_fk_expansion": True,
    "table_selection": True,
    "table_selection_style": "strict",
    "selection_keep_top": 0,
}


@dataclass(frozen=True)
class PipelineConfig:
    """
    Which pipeline features run, and with what parameters.

    Defaults reproduce the baseline. Every new feature gets a switch
    here (off by default), so it can be measured with and without it
    and the evaluator records exactly what was enabled.
    """
    # Folder name under datasets/: selects database, hints, test cases.
    dataset: str = DEFAULT_DATASET
    llm: LLMSettings = field(default_factory=LLMSettings)
    # The dataset's hints.txt appended to the schema text.
    schema_hints: bool = True
    # List the values of categorical text columns (at most
    # column_values_max distinct values) in the schema text, so the model
    # writes them as stored ('canceled', 'British'). Real data in the prompt.
    column_values: bool = False
    column_values_max: int = 50
    # Which tables the schema text lists: "full" = all of them (baseline);
    # "oracle" = only those the question's ground truth reads, an upper
    # bound for schema retrieval. The oracle needs the ground truth, so
    # only the evaluator can use it, passing a per-question schema.
    # "bm25" / "dense" / "hybrid" = the tables a retriever finds for the
    # question (see retrieval.py); the settings below apply only to these.
    schema_retrieval: str = "full"
    # Tables kept from the ranking, before bridge tables are added.
    retrieval_k: int = 5
    # Add tables on a short foreign-key path between two kept tables.
    retrieval_fk_expansion: bool = True
    # Search the database's table/column descriptions too (only
    # AdventureWorks has them).
    retrieval_descriptions: bool = False
    # Translate the question to English (with llm) before searching;
    # the SQL model still gets the original question.
    translate_for_retrieval: bool = False
    # Schema linking: after retrieval the model keeps only the candidate
    # tables the query needs (bridge tables are then added back), so the
    # SQL prompt has fewer distracting tables. Use with a larger
    # retrieval_k, so fewer needed tables are missed.
    table_selection: bool = False
    # Which selection prompt: "strict" or "inclusive" (keeps a table
    # when unsure, and tables that hold names / descriptive values).
    table_selection_style: str = "strict"
    # Safety net: the top N retrieved tables stay in the prompt whatever
    # the selection drops (0 = only the model's choice).
    selection_keep_top: int = 0
    # Ollama embedding model for "dense" and "hybrid".
    embedding_model: str = "bge-m3"
    # Reject queries that call a dangerous function (see
    # sql_function_validator). Never fires on benign analytical
    # queries, so it leaves the EX metrics unchanged.
    block_functions: bool = True
    # How many times a query that failed validation or execution is sent
    # back to the model with the error. 0 = no correction (baseline).
    max_correction_rounds: int = 0
    # After successful execution, the model turns the rows into an
    # answer in the question's language. Does not change the SQL.
    natural_language_answer: bool = False
    # At most this many result rows are shown to the answer model.
    answer_max_rows: int = 50

    def __post_init__(self):
        if self.schema_retrieval not in SCHEMA_RETRIEVAL_MODES:
            raise ValueError(
                f"Unknown schema_retrieval '{self.schema_retrieval}'. "
                f"Available: {', '.join(SCHEMA_RETRIEVAL_MODES)}"
            )
        if self.table_selection_style not in TABLE_SELECTION_TEMPLATES:
            raise ValueError(
                f"Unknown table_selection_style '{self.table_selection_style}'. "
                f"Available: {', '.join(TABLE_SELECTION_TEMPLATES)}"
            )
        if self.table_selection and self.schema_retrieval not in RETRIEVAL_METHODS:
            raise ValueError(
                "table_selection filters retrieved tables: use it with "
                f"schema_retrieval {' / '.join(RETRIEVAL_METHODS)}"
            )

    def to_dict(self):
        return asdict(self)


def open_connection(config: PipelineConfig):
    return get_connection(load_dataset(config.dataset).db_name)


def make_schema_retriever(conn, config: PipelineConfig):
    """
    The retriever for config.schema_retrieval, or None for "full" and
    "oracle". Built once per dataset and passed to every run_pipeline call.
    """
    if config.schema_retrieval not in RETRIEVAL_METHODS:
        return None

    digest = None
    if config.schema_retrieval != "bm25":
        digest = model_digest(config.embedding_model)
        if digest is None:
            raise RuntimeError(
                f"Embedding model {config.embedding_model} is not pulled: "
                f"ollama pull {config.embedding_model}"
            )

    return SchemaRetriever(
        conn,
        load_dataset(config.dataset).schemas,
        config.schema_retrieval,
        k=config.retrieval_k,
        fk_expansion=config.retrieval_fk_expansion,
        with_descriptions=config.retrieval_descriptions,
        embedding_model=config.embedding_model,
        digest=digest,
    )


def load_schema(conn, config: PipelineConfig, tables=None) -> str:
    # Schema text depends on the config, so it is built here rather
    # than by callers, which could pass a mismatching setting.
    # tables: (schema, table) pairs to list instead of all of them.
    dataset = load_dataset(config.dataset)
    hints = dataset.hints if config.schema_hints else ""
    values = (
        fetch_column_values(conn, dataset.schemas, config.column_values_max)
        if config.column_values else None
    )
    return get_schema(conn, dataset.db_name, hints, dataset.schemas, tables, values)


@dataclass
class Attempt:
    """One generated query and what happened to it."""
    sql: str
    raw_response: str
    is_valid: bool
    validation_error: str
    executed: bool
    execution_error: str
    prompt_tokens: int
    completion_tokens: int
    timings: dict

    @property
    def error(self):
        return self.validation_error or self.execution_error


@dataclass
class PipelineResult:
    """
    The top-level fields describe the final attempt; tokens and
    timings are totals over all attempts (the real cost of an answer).
    The answer's own tokens are in `answer`, its time in answer_s,
    so SQL token counts stay comparable with runs without answers.
    """
    question: str
    sql: str
    raw_response: str
    is_valid: bool
    validation_error: str
    executed: bool
    columns: list[str] | None
    rows: list | None
    execution_error: str
    prompt_tokens: int
    completion_tokens: int
    timings: dict
    attempts: list[Attempt]
    # None if the feature is off or the query did not execute.
    answer: Answer | None = None
    # Schema retrieval: the (schema, table) pairs the prompt listed
    # (None = the schema text the caller passed, e.g. every table), the
    # text that was searched with, and its translation if one was made.
    schema_tables: list | None = None
    retrieval_query: str | None = None
    translation: Translation | None = None
    # With table_selection: the retrieved candidates the model chose
    # from, and its answer (schema_tables are then its choice + bridges).
    candidate_tables: list | None = None
    table_selection: TableSelection | None = None

    @property
    def correction_rounds(self):
        return len(self.attempts) - 1

    def to_dict(self):
        return asdict(self)


def _run_attempt(conn, generation, generation_s, config):
    timings = {"generation_s": generation_s}

    start = time.perf_counter()
    is_valid, validation_error = validate_sql(
        conn, generation.sql, config.block_functions
    )
    timings["validation_s"] = time.perf_counter() - start

    columns = rows = None
    executed = False
    execution_error = ""

    if is_valid:
        start = time.perf_counter()
        try:
            columns, rows = execute_query_with_columns(conn, generation.sql)
            executed = True
        except psycopg.Error as e:
            execution_error = str(e).strip()
        timings["execution_s"] = time.perf_counter() - start

    attempt = Attempt(
        sql=generation.sql,
        raw_response=generation.raw_response,
        is_valid=is_valid,
        validation_error=validation_error,
        executed=executed,
        execution_error=execution_error,
        prompt_tokens=generation.prompt_tokens,
        completion_tokens=generation.completion_tokens,
        timings=timings,
    )

    return attempt, columns, rows


def run_pipeline(conn, question, schema, config: PipelineConfig, retriever=None) -> PipelineResult:
    """
    Question -> (schema retrieval) -> SQL generation -> validation ->
    execution, and when the query fails validation or execution, up to
    max_correction_rounds corrections with the error fed back to the
    model. Optionally a natural-language answer from the rows of the
    executed query.

    Shared by main.py and the evaluator, so what is measured is
    exactly what runs. Invalid SQL is never executed.
    schema must come from load_schema with the same config. With a
    retrieval mode, retriever (from make_schema_retriever) chooses the
    tables instead and schema is not used.
    """
    attempts = []
    pre_timings = {}
    schema_tables = retrieval_query = translation = None
    candidate_tables = selection = None

    if config.schema_retrieval in RETRIEVAL_METHODS:
        if retriever is None:
            raise ValueError(
                f"schema_retrieval '{config.schema_retrieval}' needs a retriever "
                "from make_schema_retriever"
            )

        retrieval_query = question
        if config.translate_for_retrieval:
            start = time.perf_counter()
            translation = translate_question(question, config.llm)
            pre_timings["translation_s"] = time.perf_counter() - start
            retrieval_query = translation.text

        start = time.perf_counter()
        schema_tables = retriever.select(retrieval_query)
        pre_timings["retrieval_s"] = time.perf_counter() - start

        if config.table_selection:
            start = time.perf_counter()
            candidate_tables = schema_tables
            selection = choose_tables(
                question, retriever.describe(candidate_tables), config.llm,
                config.table_selection_style,
            )
            chosen = parse_table_choice(selection.text, candidate_tables)
            # Candidates are ranked best first, so these are the top hits.
            for key in candidate_tables[:config.selection_keep_top]:
                if chosen and key not in chosen:
                    chosen.append(key)
            # An answer naming no candidate keeps them all rather than
            # leaving the prompt without tables.
            schema_tables = retriever.expand(chosen) if chosen else candidate_tables
            pre_timings["selection_s"] = time.perf_counter() - start

        schema = load_schema(conn, config, tables=schema_tables)

    start = time.perf_counter()
    generation = generate_sql(question, schema, config.llm)
    attempt, columns, rows = _run_attempt(conn, generation, time.perf_counter() - start, config)
    attempts.append(attempt)

    while not attempt.executed and len(attempts) <= config.max_correction_rounds:
        failed = [(a.raw_response, a.error) for a in attempts]

        start = time.perf_counter()
        generation = correct_sql(question, schema, failed, config.llm)
        attempt, columns, rows = _run_attempt(conn, generation, time.perf_counter() - start, config)
        attempts.append(attempt)

    timings = dict(pre_timings)
    for a in attempts:
        for key, seconds in a.timings.items():
            timings[key] = timings.get(key, 0.0) + seconds

    answer = None
    if config.natural_language_answer and attempt.executed:
        start = time.perf_counter()
        answer = generate_answer(
            question, attempt.sql, columns, rows, config.answer_max_rows, config.llm
        )
        timings["answer_s"] = time.perf_counter() - start

    return PipelineResult(
        question=question,
        sql=attempt.sql,
        raw_response=attempt.raw_response,
        is_valid=attempt.is_valid,
        validation_error=attempt.validation_error,
        executed=attempt.executed,
        columns=columns,
        rows=rows,
        execution_error=attempt.execution_error,
        prompt_tokens=sum(a.prompt_tokens for a in attempts),
        completion_tokens=sum(a.completion_tokens for a in attempts),
        timings=timings,
        attempts=attempts,
        answer=answer,
        schema_tables=schema_tables,
        retrieval_query=retrieval_query,
        translation=translation,
        candidate_tables=candidate_tables,
        table_selection=selection,
    )
