from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from .. import db, users


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
        exam_year: str | None = None,
    ):
        user = users.current_user(request)
        settings = db.ensure_user_settings(user["id"]) if user else None
        active_exam_year = exam_year or (settings or {}).get("exam_year") or "2025-26"
        rows = db.list_questions(
            topic=topic,
            source=source,
            difficulty=difficulty,
            priority=priority,
            marks=marks,
            search=q,
            exam_year=active_exam_year,
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
                "current_user": user,
                "filters": {
                    "topic": topic or "",
                    "source": source or "",
                    "difficulty": difficulty or "",
                    "priority": priority or "",
                    "marks": marks if marks is not None else "",
                    "q": q or "",
                    "exam_year": active_exam_year,
                },
            },
        )
