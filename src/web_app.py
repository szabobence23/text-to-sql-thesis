"""
Web UI: a chat over the databases.

    python src/web_app.py [--port 8000] [--no-browser]

A small FastAPI server (JSON API + the static page in src/web/), another
front-end of pipeline.run_pipeline like main.py. Every question is
answered on its own (no memory of earlier questions), with
pipeline.app_config. History is kept in a local SQLite file (chat_store).
Listens on 127.0.0.1 only: the app runs generated SQL on the databases.
"""

import argparse
import datetime
import json
import os
import threading
import time
import webbrowser
from dataclasses import dataclass
from decimal import Decimal

import psycopg
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chat_store import ChatStore
from dataset_loader import DEFAULT_DATASET, DEFAULT_LANGUAGE, available_datasets, load_dataset
from pipeline import (
    PipelineConfig,
    app_config,
    load_schema,
    make_schema_retriever,
    open_connection,
    run_pipeline,
)
from schema import fetch_catalog
from sql_tables import format_tables


WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
MAX_SAVED_ROWS = 200
TITLE_LENGTH = 48
EXAMPLE_QUESTIONS = 3


@dataclass
class Engine:
    """Everything one dataset needs; built once, shared by every request."""
    config: PipelineConfig
    conn: psycopg.Connection
    schema: str
    retriever: object
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
            table_count=table_count,
            lock=threading.Lock(),
        )
        _engines[dataset] = engine
        return engine


def jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return value.isoformat()
    return str(value)


def answer_question(dataset, question):
    """(answer text, details shown under 'Részletek')."""
    try:
        engine = get_engine(dataset)
        start = time.perf_counter()
        with engine.lock:
            result = run_pipeline(engine.conn, question, engine.schema, engine.config, engine.retriever)
        seconds = time.perf_counter() - start

    except psycopg.OperationalError as error:
        _engines.pop(dataset, None)
        return "Nem érem el az adatbázist. Fut a Docker konténer?", {"error": str(error)}
    except Exception as error:
        return "Hiba történt a kérdés feldolgozása közben. Fut az Ollama?", {"error": str(error)}

    rows = result.rows or []
    details = {
        "sql": result.sql,
        "error": result.validation_error or result.execution_error,
        "columns": result.columns,
        "rows": [[jsonable(v) for v in row] for row in rows[:MAX_SAVED_ROWS]],
        "row_count": len(rows),
        "tables": format_tables(result.schema_tables) if result.schema_tables is not None else None,
        "table_count": engine.table_count,
        "correction_rounds": result.correction_rounds,
        "seconds": round(seconds, 1),
    }

    if not result.executed:
        return (
            "Erre a kérdésre nem sikerült működő lekérdezést készítenem. "
            "Próbáld meg másképp megfogalmazni.",
            details,
        )
    if result.answer:
        return result.answer.text, details
    return "Lefutott a lekérdezés, az eredmény a részletekben látható.", details


def title_of(question):
    question = " ".join(question.split())
    return question if len(question) <= TITLE_LENGTH else question[: TITLE_LENGTH - 1] + "…"


def example_questions(dataset):
    # The first easy questions of the dataset's test set, as suggestions.
    with open(dataset.test_cases_path(DEFAULT_LANGUAGE), encoding="utf-8") as file:
        cases = json.load(file)
    easy = [case["question"] for case in cases if case.get("difficulty") == "easy"]
    return easy[:EXAMPLE_QUESTIONS]


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    dataset: str
    conversation_id: int | None = None


def create_app(store: ChatStore | None = None, answer=answer_question) -> FastAPI:
    store = store or ChatStore()
    app = FastAPI(title="Text-to-SQL", docs_url=None, redoc_url=None)

    @app.get("/api/datasets")
    def datasets():
        items = []
        for name in available_datasets():
            dataset = load_dataset(name)
            items.append({
                "name": name,
                "label": dataset.label,
                "summary": dataset.summary or dataset.description,
                "examples": example_questions(dataset),
            })
        return {"default": DEFAULT_DATASET, "datasets": items}

    @app.get("/api/conversations")
    def conversations():
        return store.list_conversations()

    @app.get("/api/conversations/{conversation_id}")
    def conversation(conversation_id: int):
        found = store.get_conversation(conversation_id)
        if found is None:
            raise HTTPException(404, "Nincs ilyen beszélgetés")
        return {**found, "messages": store.messages(conversation_id)}

    @app.delete("/api/conversations/{conversation_id}")
    def delete(conversation_id: int):
        store.delete_conversation(conversation_id)
        return {"ok": True}

    # A plain def: FastAPI runs it in a worker thread, so a slow question
    # does not block the other requests (history, page loads).
    @app.post("/api/ask")
    def ask(body: Question):
        question = body.question.strip()
        if not question:
            raise HTTPException(422, "Üres kérdés")

        if body.conversation_id is None:
            if body.dataset not in available_datasets():
                raise HTTPException(404, "Nincs ilyen adatbázis")
            dataset = body.dataset
            conversation_id = store.create_conversation(title_of(question), dataset)
        else:
            found = store.get_conversation(body.conversation_id)
            if found is None:
                raise HTTPException(404, "Nincs ilyen beszélgetés")
            # A conversation stays on the database it was started on.
            dataset = found["dataset"]
            conversation_id = body.conversation_id

        store.add_message(conversation_id, "user", question)
        text, details = answer(dataset, question)
        store.add_message(conversation_id, "assistant", text, details)

        return {
            "conversation": store.get_conversation(conversation_id),
            "message": {"role": "assistant", "content": text, "details": details},
        }

    @app.get("/")
    def index():
        return FileResponse(os.path.join(WEB_DIR, "index.html"))

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app


def main():
    parser = argparse.ArgumentParser(description="Text-to-SQL webes felület")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="ne nyissa meg a böngészőt")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    print(f"Webes felület: {url}  (leállítás: Ctrl+C)")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()

    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
