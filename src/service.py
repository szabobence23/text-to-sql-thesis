"""
The running system behind the interactive front-ends (web UI, MCP server).

One Engine per dataset (connection, schema text, retrievers, lock), built
on first use with pipeline.app_config and shared by every request.
ask() is the whole text-to-SQL system; schema_text(), find_tables(),
find_examples() and run_sql() are its parts on their own, for a client
that writes the SQL itself (the MCP server's raw tools). The front-ends
only format what these return; nothing here prints.
"""

import datetime
import threading
import time
from dataclasses import dataclass, replace
from decimal import Decimal

import psycopg

from database import execute_query_with_columns
from dataset_loader import load_dataset
from pipeline import (
    RAG_SETTINGS,
    PipelineConfig,
    PipelineResult,
    app_config,
    load_schema,
    make_example_retriever,
    make_schema_retriever,
    open_connection,
    run_pipeline,
)
from retrieval import select_tables
from schema import fetch_catalog, qualified_name
from sql_validator import validate_sql


@dataclass
class Engine:
    """Everything one dataset needs; built once, shared by every request."""
    config: PipelineConfig
    conn: psycopg.Connection
    schema: str
    retriever: object
    example_retriever: object  # few-shot examples, None when off
    tables: list  # every (schema, table), sorted
    # One query at a time: one connection, and Ollama runs one model anyway.
    lock: threading.Lock
    # find_tables' retriever: `retriever`, or one built on first use
    # where the app config does not retrieve.
    table_finder: object = None

    @property
    def table_count(self):
        return len(self.tables)


_engines = {}
_engines_lock = threading.Lock()


def get_engine(dataset) -> Engine:
    with _engines_lock:
        engine = _engines.get(dataset)
        if engine is not None and not (engine.conn.closed or engine.conn.broken):
            return engine

        conn = open_connection(PipelineConfig(dataset=dataset))
        columns, _ = fetch_catalog(conn, load_dataset(dataset).schemas)
        tables = sorted({(schema, table) for schema, table, _, _ in columns})
        config = app_config(dataset, len(tables))

        engine = Engine(
            config=config,
            conn=conn,
            schema=load_schema(conn, config),
            retriever=make_schema_retriever(conn, config),
            example_retriever=make_example_retriever(config),
            tables=tables,
            lock=threading.Lock(),
        )
        _engines[dataset] = engine
        return engine


def ask(dataset, question) -> tuple[Engine, PipelineResult, float]:
    """(engine, result, seconds) of one question; raises what the pipeline raises."""
    try:
        engine = get_engine(dataset)
        start = time.perf_counter()
        with engine.lock:
            result = run_pipeline(
                engine.conn, question, engine.schema, engine.config,
                engine.retriever, engine.example_retriever,
            )
        return engine, result, time.perf_counter() - start

    except psycopg.OperationalError:
        # Lost database: the next question builds a new engine.
        _engines.pop(dataset, None)
        raise


def resolve_tables(engine, names):
    """(schema, table) keys of table names as the schema text shows them."""
    by_name = {qualified_name(*key): key for key in engine.tables}
    unknown = [name for name in names if name.strip().lower() not in by_name]
    if unknown:
        def hint(name):
            # A bare name of a table outside public: suggest its full name.
            full = [n for n, (_, table) in by_name.items() if table == name.strip().lower()]
            return f"{name} (did you mean {' or '.join(full)}?)" if full else name
        raise ValueError(f"Unknown tables: {', '.join(hint(name) for name in unknown)}")
    return [by_name[name.strip().lower()] for name in names]


def schema_text(dataset, tables=None) -> str:
    """The schema text the model sees: every table, or only the named ones."""
    engine = get_engine(dataset)
    if not tables:
        return engine.schema
    keys = resolve_tables(engine, tables)
    with engine.lock:
        return load_schema(engine.conn, engine.config, tables=keys)


@dataclass
class TableMatch:
    name: str
    columns: tuple
    score: float
    bridge: bool  # added on a foreign-key path between two top-k tables


def find_tables(dataset, question, k) -> list[TableMatch]:
    """
    The top k tables for a question plus the bridge tables between them:
    the retrieval of pipeline.RAG_SETTINGS without the LLM table selection.
    """
    engine = get_engine(dataset)
    with engine.lock:
        if engine.table_finder is None:
            engine.table_finder = engine.retriever or make_schema_retriever(
                engine.conn, replace(engine.config, **RAG_SETTINGS)
            )
        finder = engine.table_finder
        ranking = finder.ranker.rank(question)

    top = {key for key, _ in ranking[:k]}
    scores = dict(ranking)
    docs = {doc.key: doc for doc in finder.docs}
    return [
        TableMatch(docs[key].name, docs[key].columns, scores[key], key not in top)
        for key in select_tables(ranking, k, finder.graph, fk_expansion=True)
    ]


def find_examples(dataset, question, n) -> list:
    """The n most similar solved examples (examples.Match); [] without examples.json."""
    engine = get_engine(dataset)
    if engine.example_retriever is None:
        return []
    with engine.lock:
        return engine.example_retriever.similar(question, n)


@dataclass
class SqlRun:
    error: str  # "" when the query ran; else which check or the database stopped it
    columns: list
    rows: list
    truncated: bool  # more than max_rows rows


def run_sql(dataset, sql, max_rows) -> SqlRun:
    """
    Validate and run a query written by someone else, the way the pipeline
    runs its own: the same validators, then the read-only role (rolled
    back, statement timeout). Invalid SQL is never executed.
    """
    engine = get_engine(dataset)
    with engine.lock:
        is_valid, error = validate_sql(engine.conn, sql, engine.config.block_functions)
        if not is_valid:
            return SqlRun(error, [], [], False)
        try:
            columns, rows = execute_query_with_columns(engine.conn, sql, max_rows + 1)
        except psycopg.Error as error:
            return SqlRun(f"Execution failed: {error}", [], [], False)
    return SqlRun("", columns, rows[:max_rows], len(rows) > max_rows)


def jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return value.isoformat()
    return str(value)
