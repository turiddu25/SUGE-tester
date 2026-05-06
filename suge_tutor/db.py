from __future__ import annotations

import json
import re
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
  model_answer_source TEXT,
  marking_scheme_notes TEXT,
  products_mentioned TEXT,
  related_concepts TEXT,
  is_calculation INTEGER,
  exam_technique_notes TEXT,
  figure_path TEXT,
  chains_with TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id TEXT NOT NULL,
  user_id TEXT,
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
  user_id TEXT,
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
  user_id TEXT NOT NULL,
  next_review_at TEXT NOT NULL,
  ease_level INTEGER DEFAULT 0,
  last_rating TEXT,
  last_rated_at TEXT,
  FOREIGN KEY (question_id) REFERENCES questions(id),
  UNIQUE(question_id, user_id)
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
        # Online migration: add user_id columns to pre-existing tables.
        for table in ("attempts", "exam_sessions"):
            cur.execute(f"PRAGMA table_info({table})")
            cols = {row["name"] for row in cur.fetchall()}
            if "user_id" not in cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")
        # review_queue picked up multi-user support; if it pre-dates that, drop & recreate
        # (it had no per-user data so no loss).
        cur.execute("PRAGMA table_info(review_queue)")
        cols = {row["name"] for row in cur.fetchall()}
        if cols and "user_id" not in cols:
            cur.execute("DROP TABLE review_queue")
            cur.executescript(SCHEMA)
        # Add model_answer_source / figure_path / chains_with if missing.
        cur.execute("PRAGMA table_info(questions)")
        cols = {row["name"] for row in cur.fetchall()}
        if "model_answer_source" not in cols:
            cur.execute("ALTER TABLE questions ADD COLUMN model_answer_source TEXT")
        if "figure_path" not in cols:
            cur.execute("ALTER TABLE questions ADD COLUMN figure_path TEXT")
        if "chains_with" not in cols:
            cur.execute("ALTER TABLE questions ADD COLUMN chains_with TEXT")
    _migrate_past_revision_to_revision()
    sync_questions_from_json()
    _resolve_cross_referenced_answers()


def _migrate_past_revision_to_revision() -> int:
    """Rename `past_revision_qX` -> `revision_qX` in the questions table and
    cascade the rename to attempts / review_queue rows. Idempotent: if no
    `past_revision_qX` rows exist, this is a no-op. Runs on every startup so
    that a host that pulls the new questions.json self-heals without losing
    practice history.

    FK-safe pattern: a direct UPDATE on questions.id breaks the FK in attempts
    immediately. Instead we (1) INSERT a copy with the new id, (2) re-point
    attempts and review_queue to the new id, (3) DELETE the old row. At every
    intermediate step the FK constraint is satisfied."""
    migrated = 0
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM questions WHERE id LIKE 'past_revision_q%'"
        ).fetchall()
        if not rows:
            return 0
        for row in rows:
            old = row["id"]
            new = old.replace("past_revision_q", "revision_q")
            target_exists = cur.execute(
                "SELECT 1 FROM questions WHERE id = ?", (new,)
            ).fetchone()
            if not target_exists:
                # Insert a copy with the new id. sync_questions_from_json runs
                # right after this and will overwrite the row with the canonical
                # JSON content, so we just need a row that satisfies FK.
                cur.execute(
                    """
                    INSERT INTO questions (
                      id, source, source_label, priority, topic, subtopic, difficulty,
                      marks, question_text, question_type, model_answer, model_answer_source,
                      marking_scheme_notes, products_mentioned, related_concepts,
                      is_calculation, exam_technique_notes, figure_path, chains_with
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new,
                        "revision_lecture_examples",
                        "revision_lecture_examples",
                        row["priority"],
                        row["topic"],
                        row["subtopic"],
                        row["difficulty"],
                        row["marks"],
                        row["question_text"],
                        row["question_type"],
                        row["model_answer"],
                        row["model_answer_source"] or "lecturer_paraphrased",
                        row["marking_scheme_notes"],
                        row["products_mentioned"],
                        row["related_concepts"],
                        row["is_calculation"],
                        row["exam_technique_notes"],
                        row["figure_path"] if "figure_path" in row.keys() else None,
                        row["chains_with"] if "chains_with" in row.keys() else None,
                    ),
                )
            # Now both old and new rows exist — safe to migrate references.
            cur.execute(
                "UPDATE attempts SET question_id = ? WHERE question_id = ?",
                (new, old),
            )
            cur.execute(
                "UPDATE review_queue SET question_id = ? WHERE question_id = ?",
                (new, old),
            )
            # All references migrated — safe to drop the old row.
            cur.execute("DELETE FROM questions WHERE id = ?", (old,))
            migrated += 1
    if migrated:
        print(f"[startup] migrated {migrated} past_revision_qX -> revision_qX rows")
    return migrated


def sync_questions_from_json(path: Path | None = None) -> tuple[int, int]:
    """Upsert every question from questions.json into the DB. Returns (added, updated).
    Idempotent and non-destructive — preserves attempts/reviews. Does NOT delete rows
    in the DB that are absent from JSON (so locally-added questions survive). Runs on
    every startup so machines that already have a seeded DB pick up new questions and
    content updates after a `git pull`."""
    path = path or config.QUESTIONS_JSON
    if not path.exists():
        return 0, 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    questions = payload.get("questions", payload if isinstance(payload, list) else [])
    if not questions:
        return 0, 0

    added = updated = 0
    with db_cursor() as cur:
        existing = {
            row["id"] for row in cur.execute("SELECT id FROM questions").fetchall()
        }
        for q in questions:
            mas = q.get("model_answer_source") or DEFAULT_MODEL_ANSWER_SOURCE.get(
                q.get("source"), "unknown"
            )
            chains = q.get("chains_with") or []
            cur.execute(
                """
                INSERT OR REPLACE INTO questions (
                  id, source, source_label, priority, topic, subtopic, difficulty,
                  marks, question_text, question_type, model_answer, model_answer_source,
                  marking_scheme_notes, products_mentioned, related_concepts,
                  is_calculation, exam_technique_notes, figure_path, chains_with
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    mas,
                    q.get("marking_scheme_notes"),
                    json.dumps(q.get("products_mentioned") or []),
                    json.dumps(q.get("related_concepts") or []),
                    1 if q.get("is_calculation") else 0,
                    q.get("exam_technique_notes"),
                    q.get("figure_path"),
                    json.dumps(chains) if chains else None,
                ),
            )
            if q["id"] in existing:
                updated += 1
            else:
                added += 1
    if added or updated:
        # Only log when anything actually changed — quiet on no-op startups.
        if added:
            print(f"[startup] sync_questions: {added} added, {updated} updated")
    return added, updated


_XREF_RE = re.compile(r"^\(See\s+(\w+)", re.IGNORECASE)


def _resolve_cross_referenced_answers() -> int:
    """Replace placeholder model_answers like '(See further_q7 — same answer applies.)'
    with the target question's actual model_answer. Idempotent — once resolved, the
    pattern no longer matches so subsequent calls are no-ops. Runs on every startup so
    machines that already have a seeded DB self-heal after a `git pull`."""
    fixed = 0
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT id, model_answer, source FROM questions WHERE model_answer LIKE '(See %'"
        ).fetchall()
        if not rows:
            return 0
        for row in rows:
            m = _XREF_RE.match(row["model_answer"] or "")
            if not m:
                continue
            target_id = m.group(1)
            target = cur.execute(
                "SELECT model_answer, marking_scheme_notes, model_answer_source, source, source_label FROM questions WHERE id = ?",
                (target_id,),
            ).fetchone()
            if not target or not target["model_answer"]:
                continue
            target_src = target["model_answer_source"] or DEFAULT_MODEL_ANSWER_SOURCE.get(
                target["source"], "unknown"
            )
            label = target["source_label"] or target["source"] or "the source"
            new_ma = (
                (target["model_answer"] or "")
                + f"\n\n_(This study-notes question is identical to {target_id} from the {label}. Same model answer applies.)_"
            )
            new_notes = (
                (target["marking_scheme_notes"] or "")
                + f"\n\n(Cross-reference: this is the same question as {target_id}.)"
            )
            cur.execute(
                "UPDATE questions SET model_answer = ?, marking_scheme_notes = ?, model_answer_source = ? WHERE id = ?",
                (new_ma, new_notes, target_src, row["id"]),
            )
            fixed += 1
    if fixed:
        print(f"[startup] resolved {fixed} cross-referenced model answers")
    return fixed


# Default provenance for each `source` value. Established by audit:
#   - past_paper_examples: SUGE_PastPapers.md is a Moodle outline; lecturer's worked
#     answers are video-only, so JSON model_answers were drafted by AI.
#   - further_sample_questions / sample_questions: lecturer answers exist in markdown
#     but JSON is reworded — content-faithful paraphrase.
#   - study_notes_practice: source is a PDF (unreadable from here) — flag for manual check.
DEFAULT_MODEL_ANSWER_SOURCE = {
    "past_paper_examples": "ai_generated",
    "further_sample_questions": "lecturer_paraphrased",
    "sample_questions": "lecturer_paraphrased",
    "study_notes_practice": "needs_manual_check",
    # Genuine past-paper questions sourced from the explainer-video VTTs.
    "paper_2023": "lecturer_paraphrased",
    "paper_2024": "lecturer_paraphrased",
    "paper_2025": "lecturer_paraphrased",
    # Examples Mark drew from sample/further-sample banks during the 2026 revision lecture.
    "revision_lecture_examples": "lecturer_paraphrased",
}


def load_questions_from_json(path: Path | None = None, *, replace: bool = True) -> int:
    path = path or config.QUESTIONS_JSON
    payload = json.loads(path.read_text(encoding="utf-8"))
    questions = payload.get("questions", payload if isinstance(payload, list) else [])
    with db_cursor() as cur:
        if replace:
            cur.execute("DELETE FROM questions")
        for q in questions:
            mas = q.get("model_answer_source") or DEFAULT_MODEL_ANSWER_SOURCE.get(
                q.get("source"), "unknown"
            )
            chains = q.get("chains_with") or []
            cur.execute(
                """
                INSERT OR REPLACE INTO questions (
                  id, source, source_label, priority, topic, subtopic, difficulty,
                  marks, question_text, question_type, model_answer, model_answer_source,
                  marking_scheme_notes,
                  products_mentioned, related_concepts, is_calculation, exam_technique_notes,
                  figure_path, chains_with
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    mas,
                    q.get("marking_scheme_notes"),
                    json.dumps(q.get("products_mentioned") or []),
                    json.dumps(q.get("related_concepts") or []),
                    1 if q.get("is_calculation") else 0,
                    q.get("exam_technique_notes"),
                    q.get("figure_path"),
                    json.dumps(chains) if chains else None,
                ),
            )
    return len(questions)


def row_to_question(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    d["products_mentioned"] = json.loads(d.get("products_mentioned") or "[]")
    d["related_concepts"] = json.loads(d.get("related_concepts") or "[]")
    d["chains_with"] = json.loads(d.get("chains_with") or "[]")
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
    user_id: str | None = None,
) -> int:
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO attempts (
              question_id, user_id, student_answer, marks_awarded, marks_total,
              marking_response_json, attempted_at, duration_seconds, exam_session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                question_id,
                user_id,
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


def list_attempts_for_question(qid: str, *, user_id: str | None = None) -> list[dict]:
    sql = "SELECT * FROM attempts WHERE question_id = ?"
    params: list[Any] = [qid]
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY attempted_at DESC"
    with db_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def delete_attempt(attempt_id: int, *, user_id: str | None = None) -> bool:
    """Delete a non-exam attempt. Only deletes if it belongs to user_id (when given)
    and is not part of an exam session. Returns True if a row was deleted."""
    sql = "DELETE FROM attempts WHERE id = ? AND exam_session_id IS NULL"
    params: list[Any] = [attempt_id]
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    with db_cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount > 0


def create_exam_session(
    mode: str, started_at: str, config_json: str, user_id: str | None = None
) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO exam_sessions (mode, started_at, config_json, user_id) VALUES (?, ?, ?, ?)",
            (mode, started_at, config_json, user_id),
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


# --- review queue ---------------------------------------------------------

def upsert_review(
    *,
    question_id: str,
    user_id: str,
    next_review_at: str,
    ease_level: int,
    rating: str,
    now: str,
) -> None:
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO review_queue (question_id, user_id, next_review_at, ease_level, last_rating, last_rated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(question_id, user_id) DO UPDATE SET
              next_review_at = excluded.next_review_at,
              ease_level = excluded.ease_level,
              last_rating = excluded.last_rating,
              last_rated_at = excluded.last_rated_at
            """,
            (question_id, user_id, next_review_at, ease_level, rating, now),
        )


def get_review(question_id: str, user_id: str) -> dict | None:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM review_queue WHERE question_id = ? AND user_id = ?",
            (question_id, user_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def due_reviews(user_id: str, now: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT r.*, q.topic, q.marks, q.priority, q.question_text
            FROM review_queue r
            JOIN questions q ON q.id = r.question_id
            WHERE r.user_id = ? AND r.next_review_at <= ?
            ORDER BY r.next_review_at ASC
            """,
            (user_id, now),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def upcoming_reviews(user_id: str, limit: int = 20) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT r.*, q.topic, q.marks, q.priority, q.question_text
            FROM review_queue r
            JOIN questions q ON q.id = r.question_id
            WHERE r.user_id = ?
            ORDER BY r.next_review_at ASC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# --- progress / dashboard helpers ---------------------------------------

def attempts_for_user(user_id: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM attempts WHERE user_id = ? ORDER BY attempted_at DESC",
            (user_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def latest_attempt_per_question(user_id: str) -> list[dict]:
    """One row per question, with the user's most recent attempt joined to question metadata."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT a.*, q.topic, q.marks, q.priority, q.question_text
            FROM attempts a
            JOIN questions q ON q.id = a.question_id
            WHERE a.user_id = ? AND a.id IN (
              SELECT MAX(id) FROM attempts WHERE user_id = ? GROUP BY question_id
            )
            ORDER BY a.attempted_at DESC
            """,
            (user_id, user_id),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def topic_averages(user_id: str) -> list[dict]:
    """Average percentage per topic, using each question's most recent attempt."""
    with db_cursor() as cur:
        cur.execute(
            """
            WITH latest AS (
              SELECT a.question_id, a.marks_awarded, a.marks_total
              FROM attempts a
              WHERE a.user_id = ? AND a.id IN (
                SELECT MAX(id) FROM attempts WHERE user_id = ? GROUP BY question_id
              )
            )
            SELECT q.topic AS topic,
                   COUNT(*) AS n,
                   AVG(CASE WHEN l.marks_total > 0 AND l.marks_awarded IS NOT NULL
                            THEN 100.0 * l.marks_awarded / l.marks_total ELSE NULL END) AS avg_pct
            FROM latest l
            JOIN questions q ON q.id = l.question_id
            GROUP BY q.topic
            ORDER BY avg_pct ASC
            """,
            (user_id, user_id),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def attempts_today(user_id: str, day_start_iso: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS c FROM attempts WHERE user_id = ? AND attempted_at >= ?",
            (user_id, day_start_iso),
        )
        row = cur.fetchone()
    return int(row["c"]) if row else 0


def attempts_total(user_id: str) -> int:
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM attempts WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
    return int(row["c"]) if row else 0


def recent_attempts(user_id: str, limit: int = 50) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT a.attempted_at, a.marks_awarded, a.marks_total, q.topic
            FROM attempts a
            JOIN questions q ON q.id = a.question_id
            WHERE a.user_id = ?
            ORDER BY a.attempted_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def best_exam_session(user_id: str) -> dict | None:
    """Most recent finished exam session for the user, with computed percentage."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT * FROM exam_sessions
            WHERE user_id = ? AND finished_at IS NOT NULL AND total_marks_possible > 0
            ORDER BY (total_marks_awarded / total_marks_possible) DESC, finished_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["percentage"] = round(100.0 * d["total_marks_awarded"] / d["total_marks_possible"], 1)
    return d


def attempted_question_ids(user_id: str) -> set[str]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT DISTINCT question_id FROM attempts WHERE user_id = ?",
            (user_id,),
        )
        rows = cur.fetchall()
    return {r["question_id"] for r in rows}
