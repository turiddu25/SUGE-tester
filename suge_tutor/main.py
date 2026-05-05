from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db
from .config import config
from .routes import exam, practice, questions

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


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "question_count": db.question_count(),
            "config": {
                "provider": config.LLM_PROVIDER,
                "model": config.LLM_MODEL,
                "api_key_set": bool(config.LLM_API_KEY),
            },
        },
    )


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse({"error": "not found", "path": str(request.url)}, status_code=404)


# Wire up sub-routers; they get the templates instance lazily.
questions.register(app, templates)
practice.register(app, templates)
exam.register(app, templates)
