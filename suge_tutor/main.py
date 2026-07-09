from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db, users
from .config import config
from .routes import auth, cribsheet, exam, practice, products, questions, reference, review
from .spaced_repetition import days_to_exam

BASE_DIR = config.PROJECT_ROOT
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# Cache-bust query string for our /static/* assets — bumps on every server restart
# so a fresh `uvicorn` is enough to evict stale JS/CSS from the browser.
templates.env.globals["STATIC_V"] = str(int(time.time()))
# Make total LLM spend available in every template (used in the base footer).
# This is a callable so templates re-query each render — the underlying SUM is
# trivial and we don't want a stale figure.
templates.env.globals["llm_spend"] = db.llm_spend_summary


@asynccontextmanager
async def lifespan(app: FastAPI):
    # init_schema runs the column migrations, the past_revision -> revision rename,
    # syncs questions.json into the DB (upsert, non-destructive), and resolves any
    # cross-referenced model answers. Idempotent — safe to run on every boot.
    db.init_schema()
    yield


app = FastAPI(title="SUGE Tutor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def home(request: Request):
    user = users.current_user(request)
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    today_count = db.attempts_today(user["id"], day_start) if user else 0
    user_settings = db.ensure_user_settings(user["id"]) if user else None
    total_count = db.attempts_total(user["id"]) if user else 0
    topic_avgs = db.topic_averages(user["id"]) if user else []
    weakest = topic_avgs[0] if topic_avgs else None

    # Rolling-average chart data: bucket recent attempts by day & topic.
    series = _rolling_average_series(user["id"]) if user else {"labels": [], "datasets": []}

    # Recommended next: 3 from due reviews + 1 unattempted from weakest topic.
    recommended: list[dict] = []
    if user:
        due = db.due_reviews(user["id"], now.isoformat())[:3]
        for r in due:
            recommended.append(
                {
                    "id": r["question_id"],
                    "topic": r["topic"],
                    "marks": r["marks"],
                    "question_text": r["question_text"],
                    "reason": f"Due review · {r.get('last_rating') or '—'}",
                }
            )
        if weakest:
            done = db.attempted_question_ids(user["id"])
            for q in db.list_questions(topic=weakest["topic"]):
                if q["id"] in done:
                    continue
                recommended.append(
                    {
                        "id": q["id"],
                        "topic": q["topic"],
                        "marks": q["marks"],
                        "question_text": q["question_text"],
                        "reason": f"Fresh — your weakest topic ({weakest['topic']})",
                    }
                )
                break

    # Grade target context
    best_exam = db.best_exam_session(user["id"]) if user else None
    grade_status = (
        users.grade_for(best_exam["percentage"], user["grade_targets"])
        if user and best_exam
        else None
    )
    grade_targets_display = []
    if user and user.get("grade_targets"):
        grade_targets_display = sorted(
            [
                (grade, target)
                for grade, target in user["grade_targets"].items()
                if grade in {"A5", "B3", "C3"} and isinstance(target, (int, float))
            ],
            key=lambda item: item[1],
            reverse=True,
        )

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "question_count": db.question_count(),
            "current_user": user,
            "user_settings": user_settings,
            "today_count": today_count,
            "total_count": total_count,
            "topic_avgs": topic_avgs,
            "weakest": weakest,
            "series": series,
            "recommended": recommended,
            "best_exam": best_exam,
            "grade_status": grade_status,
            "grade_targets_display": grade_targets_display,
            "days_to_exam": days_to_exam(),
            "exam_date": config.EXAM_DATE,
            "config": {
                "provider": config.LLM_PROVIDER,
                "model": config.LLM_MODEL,
                "api_key_set": bool(config.LLM_API_KEY),
            },
        },
    )


def _rolling_average_series(user_id: str, *, days: int = 14) -> dict:
    """Per-topic rolling daily average for the last N days, ready for Chart.js."""
    rows = db.recent_attempts(user_id, limit=500)
    if not rows:
        return {"labels": [], "datasets": []}
    today = datetime.now(timezone.utc).date()
    labels = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    label_set = set(labels)
    by_topic_day: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        if r.get("marks_awarded") is None or not r.get("marks_total"):
            continue
        try:
            day = datetime.fromisoformat(r["attempted_at"]).date().isoformat()
        except ValueError:
            continue
        if day not in label_set:
            continue
        pct = 100.0 * float(r["marks_awarded"]) / float(r["marks_total"])
        by_topic_day.setdefault(r["topic"], {}).setdefault(day, []).append(pct)
    palette = ["#4f46e5", "#0891b2", "#16a34a", "#d97706", "#db2777"]
    datasets = []
    for i, (topic, by_day) in enumerate(sorted(by_topic_day.items())):
        data = []
        for label in labels:
            samples = by_day.get(label)
            data.append(round(sum(samples) / len(samples), 1) if samples else None)
        datasets.append({"label": topic, "data": data, "color": palette[i % len(palette)]})
    return {"labels": labels, "datasets": datasets}


@app.get("/api/llm/balance")
async def api_llm_balance():
    """Surface the remaining USD/GBP balance from Moonshot's official
    /v1/users/me/balance endpoint. Cached 60s in the marking module."""
    from .marking import fetch_balance
    data = await fetch_balance()
    return JSONResponse(data)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse({"error": "not found", "path": str(request.url)}, status_code=404)


# Wire up sub-routers; they get the templates instance lazily.
auth.register(app, templates)
questions.register(app, templates)
practice.register(app, templates)
exam.register(app, templates)
review.register(app, templates)
reference.register(app, templates)
products.register(app, templates)
cribsheet.register(app, templates)
