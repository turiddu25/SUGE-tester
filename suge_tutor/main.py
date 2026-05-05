from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db, users
from .config import config
from .routes import auth, exam, practice, products, questions, reference, review

BASE_DIR = config.PROJECT_ROOT
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_schema()
    if db.question_count() == 0 and config.QUESTIONS_JSON.exists():
        n = db.load_questions_from_json()
        print(f"[startup] seeded {n} questions from {config.QUESTIONS_JSON.name}")
    yield


app = FastAPI(title="SUGE Tutor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Pages that don't require a picked user.
_OPEN_PATHS = {"/users", "/users/logout"}
_OPEN_PREFIXES = ("/users/switch/", "/static/")


@app.middleware("http")
async def require_user_middleware(request: Request, call_next):
    path = request.url.path
    if (
        path in _OPEN_PATHS
        or any(path.startswith(p) for p in _OPEN_PREFIXES)
        or path.startswith("/api/")  # APIs return JSON; client passes the cookie anyway
    ):
        return await call_next(request)
    if users.current_user(request) is None:
        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"
        return RedirectResponse(url=f"/users?next={next_url}", status_code=303)
    return await call_next(request)


@app.get("/")
async def home(request: Request):
    user = users.current_user(request)
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    today_count = db.attempts_today(user["id"], day_start) if user else 0
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

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "question_count": db.question_count(),
            "current_user": user,
            "today_count": today_count,
            "total_count": total_count,
            "topic_avgs": topic_avgs,
            "weakest": weakest,
            "series": series,
            "recommended": recommended,
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
