from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from .. import db
from ..marking import mark_answer
from ..models import MarkRequest


def register(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.get("/practice/{question_id}")
    async def practice_view(question_id: str, request: Request):
        question = db.get_question(question_id)
        if not question:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")

        recommended_minutes = round(int(question["marks"]) * 1.75, 1)
        history = db.list_attempts_for_question(question_id)
        return templates.TemplateResponse(
            request,
            "practice.html",
            {
                "question": question,
                "recommended_minutes": recommended_minutes,
                "history": history,
            },
        )

    @app.post("/api/mark")
    async def api_mark(payload: MarkRequest):
        question = db.get_question(payload.question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        result = await mark_answer(question, payload.student_answer)
        attempted_at = datetime.now(timezone.utc).isoformat()

        marks_awarded = result.get("marks_awarded") if not result.get("error") else None
        marks_total = result.get("marks_total") or question.get("marks")

        attempt_id = db.insert_attempt(
            question_id=payload.question_id,
            student_answer=payload.student_answer,
            marks_awarded=float(marks_awarded) if isinstance(marks_awarded, (int, float)) else None,
            marks_total=int(marks_total) if marks_total is not None else None,
            marking_response_json=json.dumps(result, ensure_ascii=False),
            attempted_at=attempted_at,
            duration_seconds=payload.duration_seconds,
            exam_session_id=payload.exam_session_id,
        )

        return JSONResponse({"attempt_id": attempt_id, "result": result})
