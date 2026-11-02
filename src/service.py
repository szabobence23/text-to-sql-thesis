"""
The running system behind the interactive front-ends (web UI, MCP server).

One Engine per dataset (connection, schema text, retrievers, lock), built
on first use with pipeline.app_config and shared by every request. The
front-ends only format what ask() returns; nothing here prints.
"""

import datetime
import threading
import time
from dataclasses import dataclass
from decimal import Decimal

import psycopg

from dataset_loader import load_dataset
from pipeline import (
    PipelineConfig,
    PipelineResult,
    app_config,
    load_schema,
    make_example_retriever,
    make_schema_retriever,
    open_connection,
    run_pipeline,
)
from schema import fetch_catalog


@dataclass
class Engine:
    """Everything one dataset needs; built once, shared by every request."""
    config: PipelineConfig
    conn: psycopg.Connection
    schema: str
    retriever: object
    example_retriever: object  # few-shot examples, None when off
    table_count: int
    # One query at a time: one connection, and Ollama runs one model anyway.
    lock: threading.Lock


_engines = {}
_engines_lock = threading.Lock()


def get_engine(dataset) -> Engine:
    with _engines_lock:
        engine = _engines.get(dataset)
        if engine is not None and not (engine.conn.closed or engine.conn.broken):
            return engine

        conn = open_connection(PipelineConfig(dataset=dataset))
        columns, _ = fetch_catalog(conn, load_dataset(dataset).schemas)
        table_count = len({(schema, table) for schema, table, _, _ in columns})
        config = app_config(dataset, table_count)

        engine = Engine(
            config=config,
            conn=conn,
            schema=load_schema(conn, config),
            retriever=make_schema_retriever(conn, config),
            example_retriever=make_example_retriever(config),
            table_count=table_count,
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


def jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return value.isoformat()
    return str(value)
