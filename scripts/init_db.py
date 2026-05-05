"""Initialise SQLite DB and load seed questions.

Usage:
    python scripts/init_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from suge_tutor import db
from suge_tutor.config import config


def main() -> None:
    print(f"DB path: {config.DB_PATH}")
    db.init_schema()
    print("Schema ready.")
    if not config.QUESTIONS_JSON.exists():
        print(f"WARNING: {config.QUESTIONS_JSON} not found — skipping seed.")
        return
    n = db.load_questions_from_json()
    print(f"Loaded {n} questions from {config.QUESTIONS_JSON.name}.")
    print(f"DB now has {db.question_count()} questions.")


if __name__ == "__main__":
    main()
