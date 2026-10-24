"""
Chat history of the web UI (web_app.py) in a local SQLite file.

Not in PostgreSQL: the application role is read-only, and the history
belongs to the application, not to any dataset. One connection per
operation, so Streamlit's threads never share one.
"""

import datetime
import json
import os
import sqlite3
from contextlib import closing

from dataset_loader import REPO_DIR


DEFAULT_PATH = os.path.join(REPO_DIR, ".chat_history", "chats.sqlite3")

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    dataset TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL
);
"""


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


class ChatStore:
    def __init__(self, path=DEFAULT_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_conversation(self, title, dataset) -> int:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT INTO conversations (title, dataset, created_at) VALUES (?, ?, ?)",
                (title, dataset, _now()),
            )
            return cursor.lastrowid

    def list_conversations(self) -> list[dict]:
        # Most recently used first: by the latest message (ids only grow,
        # timestamps can tie within a second).
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT c.id, c.title, c.dataset, c.created_at FROM conversations AS c "
                "ORDER BY COALESCE((SELECT MAX(m.id) FROM messages AS m "
                "WHERE m.conversation_id = c.id), 0) DESC, c.id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id) -> dict | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id, title, dataset, created_at FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        return dict(row) if row else None

    def add_message(self, conversation_id, role, content, details=None):
        # details: JSON-serialisable dict (SQL, rows, ...) for the assistant.
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, details, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    role,
                    content,
                    json.dumps(details, ensure_ascii=False) if details is not None else None,
                    _now(),
                ),
            )

    def messages(self, conversation_id) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT role, content, details, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        return [
            {**dict(row), "details": json.loads(row["details"]) if row["details"] else None}
            for row in rows
        ]

    def delete_conversation(self, conversation_id):
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
