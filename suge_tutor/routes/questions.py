from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from .. import db


def register(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.get("/questions")
    async def questions_list(
        request: Request,
        topic: str | None = None,
        source: str | None = None,
        difficulty: str | None = None,
        priority: str | None = None,
        marks: int | None = None,
        q: str | None = None,
    ):
        rows = db.list_questions(
            topic=topic,
            source=source,
            difficulty=difficulty,
            priority=priority,
            marks=marks,
            search=q,
        )
        topics = sorted({r["topic"] for r in rows} | {
            "activation_retention",
            "compounding_growth",
            "acquisition",
            "organisation",
            "investment",
        })
        sources = sorted({r["source"] for r in rows} | {
            "past_paper_examples",
            "further_sample_questions",
            "sample_questions",
            "study_notes_practice",
        })
        return templates.TemplateResponse(
            request,
            "questions_list.html",
            {
                "questions": rows,
                "topics": topics,
                "sources": sources,
                "filters": {
                    "topic": topic or "",
                    "source": source or "",
                    "difficulty": difficulty or "",
                    "priority": priority or "",
                    "marks": marks if marks is not None else "",
                    "q": q or "",
                },
            },
        )
