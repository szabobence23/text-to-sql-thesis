"""
Web UI: a chat over the databases.

    python src/web_app.py [--port 8000] [--no-browser]

A small FastAPI server (JSON API + the static page in src/web/), another
front-end of pipeline.run_pipeline like main.py. Every question is
answered on its own (no memory of earlier questions), by the shared
engines of service.py (pipeline.app_config). History is kept in a local
SQLite file (chat_store). Listens on 127.0.0.1 only: the app runs
generated SQL on the databases.
"""

import argparse
import json
import os
import threading
import webbrowser
from typing import Literal

import psycopg
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import service
from chat_store import ChatStore
from dataset_loader import DEFAULT_DATASET, DEFAULT_LANGUAGE, available_datasets, load_dataset
from service import jsonable
from sql_tables import format_tables


WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
MAX_SAVED_ROWS = 200
TITLE_LENGTH = 48
EXAMPLE_QUESTIONS = 3

# Languages of the interface. The model answers in the question's
# language whatever is chosen here; these are the app's own messages.
UI_LANGUAGES = ("hu", "en")
MESSAGES = {
    "hu": {
        "no_database": "Nem érem el az adatbázist. Fut a Docker konténer?",
        "error": "Hiba történt a kérdés feldolgozása közben. Fut az Ollama?",
        "failed": "Erre a kérdésre nem sikerült működő lekérdezést készítenem. "
                  "Próbáld meg másképp megfogalmazni.",
        "no_answer": "Lefutott a lekérdezés, az eredmény a részletekben látható.",
    },
    "en": {
        "no_database": "I cannot reach the database. Is the Docker container running?",
        "error": "Something went wrong while processing the question. Is Ollama running?",
        "failed": "I could not write a working query for this question. "
                  "Try rephrasing it.",
        "no_answer": "The query ran; the result is shown in the details.",
    },
}


def answer_question(dataset, question, language="hu"):
    """(answer text, details shown under 'Details'); language: the UI's."""
    messages = MESSAGES[language]
    try:
        engine, result, seconds = service.ask(dataset, question)
    except psycopg.OperationalError as error:
        return messages["no_database"], {"error": str(error)}
    except Exception as error:
        return messages["error"], {"error": str(error)}

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
        # The answer model's verdict on the result (None: no verdict).
        "doubtful": result.answer.doubtful if result.answer else None,
        # For the debug view: what happened step by step.
        "attempts": [{"sql": a.sql, "error": a.error} for a in result.attempts],
        "sql_examples": result.sql_examples,
        "candidate_tables": (
            format_tables(result.candidate_tables) if result.candidate_tables is not None else None
        ),
        "timings": {key: round(value, 2) for key, value in result.timings.items()},
        "tokens": {
            "prompt": result.prompt_tokens,
            "completion": result.completion_tokens,
            "answer": (
                result.answer.prompt_tokens + result.answer.completion_tokens if result.answer else 0
            ),
        },
        "config": {
            "schema_retrieval": engine.config.schema_retrieval,
            "table_selection": engine.config.table_selection,
            "max_correction_rounds": engine.config.max_correction_rounds,
            "sql_examples": engine.config.sql_examples,
            "model": engine.config.llm.model,
        },
    }

    if not result.executed:
        return messages["failed"], details
    if result.answer:
        return result.answer.text, details
    return messages["no_answer"], details


def title_of(question):
    question = " ".join(question.split())
    return question if len(question) <= TITLE_LENGTH else question[: TITLE_LENGTH - 1] + "…"


def example_questions(dataset, language):
    # The first easy questions of the dataset's test set, as suggestions.
    if language not in dataset.languages:
        language = DEFAULT_LANGUAGE
    with open(dataset.test_cases_path(language), encoding="utf-8") as file:
        cases = json.load(file)
    easy = [case["question"] for case in cases if case.get("difficulty") == "easy"]
    return easy[:EXAMPLE_QUESTIONS]


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    dataset: str
    conversation_id: int | None = None
    language: Literal["hu", "en"] = "hu"


def create_app(store: ChatStore | None = None, answer=answer_question) -> FastAPI:
    store = store or ChatStore()
    app = FastAPI(title="Text-to-SQL", docs_url=None, redoc_url=None)

    @app.get("/api/datasets")
    def datasets(language: Literal["hu", "en"] = "hu"):
        items = []
        for name in available_datasets():
            dataset = load_dataset(name)
            items.append({
                "name": name,
                "label": dataset.label(language),
                "summary": dataset.summary(language),
                "examples": example_questions(dataset, language),
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
        text, details = answer(dataset, question, body.language)
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
