"""
Persistencia de sesiones y feedback en SQLite.

- sessions: historial de mensajes por student_id.
- feedback: 👍/👎 sobre respuestas para fine-tune posterior.
"""
from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from src.config import SESSIONS_DIR

_DB_PATH = SESSIONS_DIR / "sessions.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                ts REAL NOT NULL
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_student
            ON messages(student_id, ts)
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                rating INTEGER NOT NULL,
                llm_model TEXT,
                citations_json TEXT,
                comment TEXT,
                ts REAL NOT NULL
            )
        """)


def save_message(student_id: str, role: str, content: str) -> None:
    init_db()
    with _conn() as c:
        c.execute(
            "INSERT INTO messages(student_id, role, content, ts) VALUES(?, ?, ?, ?)",
            (str(student_id), role, content, time.time()),
        )


def load_history(student_id: str, limit: int = 50) -> List[dict]:
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content, ts FROM messages "
            "WHERE student_id = ? ORDER BY ts ASC LIMIT ?",
            (str(student_id), limit),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_history(student_id: str) -> None:
    init_db()
    with _conn() as c:
        c.execute("DELETE FROM messages WHERE student_id = ?", (str(student_id),))


def save_feedback(
    student_id: str,
    query: str,
    response: str,
    rating: int,  # 1 = 👍, -1 = 👎
    llm_model: Optional[str] = None,
    citations: Optional[list] = None,
    comment: Optional[str] = None,
) -> None:
    init_db()
    with _conn() as c:
        c.execute(
            "INSERT INTO feedback(student_id, query, response, rating, llm_model, "
            "citations_json, comment, ts) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(student_id), query, response, int(rating),
                llm_model, json.dumps(citations) if citations else None,
                comment, time.time(),
            ),
        )
