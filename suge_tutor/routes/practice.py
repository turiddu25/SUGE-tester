from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

import random as _random

from fastapi.responses import RedirectResponse

from .. import db, users
from ..marking import mark_answer
from ..models import MarkRequest


def register(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.get("/practice/random")
    async def practice_random(
        request: Request,
        topic: str | None = None,
        source: str | None = None,
        difficulty: str | None = None,
        priority: str | None = None,
    ):
        pool = db.list_questions(
            topic=topic,
            source=source,
            difficulty=difficulty,
            priority=priority,
        )
        if not pool:
            return RedirectResponse(url="/questions", status_code=303)
        pick = _random.choice(pool)
        return RedirectResponse(url=f"/practice/{pick['id']}", status_code=303)

    @app.get("/practice/{question_id}")
    async def practice_view(question_id: str, request: Request):
        question = db.get_question(question_id)
        if not question:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")

        recommended_minutes = round(int(question["marks"]) * 1.75, 1)
        user = users.current_user(request)
        history = db.list_attempts_for_question(
            question_id, user_id=user["id"] if user else None
        )
        return templates.TemplateResponse(
            request,
            "practice.html",
            {
                "question": question,
                "recommended_minutes": recommended_minutes,
                "history": history,
                "current_user": user,
            },
        )

    @app.delete("/api/attempts/{attempt_id}")
    async def api_delete_attempt(attempt_id: int, request: Request):
        user = users.current_user(request)
        ok = db.delete_attempt(attempt_id, user_id=user["id"] if user else None)
        if not ok:
            raise HTTPException(status_code=404, detail="Attempt not found or not deletable")
        return JSONResponse({"deleted": attempt_id})

    @app.post("/api/mark")
    async def api_mark(payload: MarkRequest, request: Request):
        question = db.get_question(payload.question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        result = await mark_answer(question, payload.student_answer)
        attempted_at = datetime.now(timezone.utc).isoformat()

        marks_awarded = result.get("marks_awarded") if not result.get("error") else None
        marks_total = result.get("marks_total") or question.get("marks")

        user = users.current_user(request)
        attempt_id = db.insert_attempt(
            question_id=payload.question_id,
            student_answer=payload.student_answer,
            marks_awarded=float(marks_awarded) if isinstance(marks_awarded, (int, float)) else None,
            marks_total=int(marks_total) if marks_total is not None else None,
            marking_response_json=json.dumps(result, ensure_ascii=False),
            attempted_at=attempted_at,
            duration_seconds=payload.duration_seconds,
            exam_session_id=payload.exam_session_id,
            user_id=user["id"] if user else None,
        )

        return JSONResponse({"attempt_id": attempt_id, "result": result})
