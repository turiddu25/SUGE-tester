from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

from .config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  source_label TEXT,
  priority TEXT,
  topic TEXT NOT NULL,
  subtopic TEXT,
  difficulty TEXT,
  marks INTEGER NOT NULL,
  question_text TEXT NOT NULL,
  question_type TEXT,
  model_answer TEXT,
  marking_scheme_notes TEXT,
  products_mentioned TEXT,
  related_concepts TEXT,
  is_calculation INTEGER,
  exam_technique_notes TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id TEXT NOT NULL,
  student_answer TEXT NOT NULL,
  marks_awarded REAL,
  marks_total INTEGER,
  marking_response_json TEXT,
  attempted_at TEXT NOT NULL,
  duration_seconds INTEGER,
  exam_session_id INTEGER,
  flagged_for_review INTEGER DEFAULT 0,
  FOREIGN KEY (question_id) REFERENCES questions(id)
);

CREATE TABLE IF NOT EXISTS exam_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mode TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  total_marks_awarded REAL,
  total_marks_possible INTEGER,
  config_json TEXT
);

CREATE TABLE IF NOT EXISTS review_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id TEXT NOT NULL,
  next_review_at TEXT NOT NULL,
  ease_level INTEGER DEFAULT 0,
  FOREIGN KEY (question_id) REFERENCES questions(id),
  UNIQUE(question_id)
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_cursor() -> Iterator[sqlite3.Cursor]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


def init_schema() -> None:
    with db_cursor() as cur:
        cur.executescript(SCHEMA)


def load_questions_from_json(path: Path | None = None, *, replace: bool = True) -> int:
    path = path or config.QUESTIONS_JSON
    payload = json.loads(path.read_text(encoding="utf-8"))
    questions = payload.get("questions", payload if isinstance(payload, list) else [])
    with db_cursor() as cur:
        if replace:
            cur.execute("DELETE FROM questions")
        for q in questions:
            cur.execute(
                """
                INSERT OR REPLACE INTO questions (
                  id, source, source_label, priority, topic, subtopic, difficulty,
                  marks, question_text, question_type, model_answer, marking_scheme_notes,
                  products_mentioned, related_concepts, is_calculation, exam_technique_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    q.get("id"),
                    q.get("source"),
                    q.get("source_label"),
                    q.get("priority"),
                    q.get("topic"),
                    q.get("subtopic"),
                    q.get("difficulty"),
                    int(q.get("marks", 0)),
                    q.get("question_text"),
                    q.get("question_type"),
                    q.get("model_answer"),
                    q.get("marking_scheme_notes"),
                    json.dumps(q.get("products_mentioned") or []),
                    json.dumps(q.get("related_concepts") or []),
                    1 if q.get("is_calculation") else 0,
                    q.get("exam_technique_notes"),
                ),
            )
    return len(questions)


def row_to_question(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    d["products_mentioned"] = json.loads(d.get("products_mentioned") or "[]")
    d["related_concepts"] = json.loads(d.get("related_concepts") or "[]")
    d["is_calculation"] = bool(d.get("is_calculation"))
    return d


def list_questions(
    *,
    topic: str | None = None,
    source: str | None = None,
    difficulty: str | None = None,
    priority: str | None = None,
    marks: int | None = None,
    search: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM questions WHERE 1=1"
    params: list[Any] = []
    if topic:
        sql += " AND topic = ?"
        params.append(topic)
    if source:
        sql += " AND source = ?"
        params.append(source)
    if difficulty:
        sql += " AND difficulty = ?"
        params.append(difficulty)
    if priority:
        sql += " AND priority = ?"
        params.append(priority)
    if marks is not None:
        sql += " AND marks = ?"
        params.append(marks)
    if search:
        sql += " AND (question_text LIKE ? OR subtopic LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])
    sql += " ORDER BY CASE priority WHEN 'highest' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, marks DESC, id"
    with db_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [row_to_question(r) for r in rows]  # type: ignore[misc]


def get_question(qid: str) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM questions WHERE id = ?", (qid,))
        row = cur.fetchone()
    return row_to_question(row)


def get_questions_by_ids(ids: Iterable[str]) -> list[dict]:
    ids = list(ids)
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    with db_cursor() as cur:
        cur.execute(f"SELECT * FROM questions WHERE id IN ({placeholders})", ids)
        rows = cur.fetchall()
    by_id = {r["id"]: row_to_question(r) for r in rows}
    return [by_id[i] for i in ids if i in by_id]


def insert_attempt(
    *,
    question_id: str,
    student_answer: str,
    marks_awarded: float | None,
    marks_total: int | None,
    marking_response_json: str,
    attempted_at: str,
    duration_seconds: int | None = None,
    exam_session_id: int | None = None,
) -> int:
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO attempts (
              question_id, student_answer, marks_awarded, marks_total,
              marking_response_json, attempted_at, duration_seconds, exam_session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                question_id,
                student_answer,
                marks_awarded,
                marks_total,
                marking_response_json,
                attempted_at,
                duration_seconds,
                exam_session_id,
            ),
        )
        return cur.lastrowid or 0


def list_attempts_for_question(qid: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM attempts WHERE question_id = ? ORDER BY attempted_at DESC",
            (qid,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def create_exam_session(mode: str, started_at: str, config_json: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO exam_sessions (mode, started_at, config_json) VALUES (?, ?, ?)",
            (mode, started_at, config_json),
        )
        return cur.lastrowid or 0


def finalize_exam_session(
    session_id: int,
    *,
    finished_at: str,
    total_marks_awarded: float,
    total_marks_possible: int,
) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE exam_sessions SET finished_at = ?, total_marks_awarded = ?, total_marks_possible = ? WHERE id = ?",
            (finished_at, total_marks_awarded, total_marks_possible, session_id),
        )


def get_exam_session(session_id: int) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM exam_sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def get_session_attempts(session_id: int) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM attempts WHERE exam_session_id = ? ORDER BY id",
            (session_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def question_count() -> int:
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM questions")
        row = cur.fetchone()
    return int(row["c"]) if row else 0
