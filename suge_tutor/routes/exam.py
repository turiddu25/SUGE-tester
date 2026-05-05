from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from .. import db, users
from ..config import config
from ..exam_selector import select_exam_questions, topic_breakdown, TARGET_TOPIC_MARKS
from ..marking import mark_answer
from ..models import ExamSubmitRequest


def register(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.get("/exam-sim")
    async def exam_setup(request: Request):
        return templates.TemplateResponse(
            request,
            "exam_setup.html",
            {
                "topic_targets": TARGET_TOPIC_MARKS,
                "current_user": users.current_user(request),
            },
        )

    @app.post("/exam-sim/start")
    async def exam_start(request: Request):
        form = await request.form()
        seed_str = form.get("seed", "").strip()
        seed = int(seed_str) if seed_str else None
        questions = select_exam_questions(seed=seed)
        if not questions:
            raise HTTPException(status_code=500, detail="No questions available")

        started_at = datetime.now(timezone.utc).isoformat()
        cfg = {
            "seed": seed,
            "question_ids": [q["id"] for q in questions],
            "topic_breakdown": topic_breakdown(questions),
            "total_marks": sum(int(q["marks"]) for q in questions),
            "duration_minutes": 105,
        }
        user = users.current_user(request)
        session_id = db.create_exam_session(
            mode="exam_simulation",
            started_at=started_at,
            config_json=json.dumps(cfg),
            user_id=user["id"] if user else None,
        )

        return templates.TemplateResponse(
            request,
            "exam_active.html",
            {
                "session_id": session_id,
                "questions": questions,
                "total_marks": cfg["total_marks"],
                "topic_breakdown": cfg["topic_breakdown"],
                "duration_seconds": 105 * 60,
                "current_user": user,
            },
        )

    @app.post("/api/exam/submit")
    async def exam_submit(payload: ExamSubmitRequest, request: Request):
        session = db.get_exam_session(payload.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Exam session not found")

        user = users.current_user(request)
        question_ids = [item.question_id for item in payload.items]
        questions = {q["id"]: q for q in db.get_questions_by_ids(question_ids)}

        sem = asyncio.Semaphore(max(1, config.LLM_CONCURRENCY))

        async def mark_one(item):
            q = questions.get(item.question_id)
            if not q:
                return item.question_id, {"error": "missing_question", "raw_response": ""}
            async with sem:
                result = await mark_answer(q, item.answer)
            return item.question_id, result

        tasks = [mark_one(item) for item in payload.items]
        outcomes = await asyncio.gather(*tasks)

        attempted_at = datetime.now(timezone.utc).isoformat()
        per_question = []
        total_awarded = 0.0
        total_possible = 0
        results_by_id = dict(outcomes)

        for item in payload.items:
            q = questions.get(item.question_id)
            if not q:
                continue
            res = results_by_id.get(item.question_id, {})
            awarded = res.get("marks_awarded") if not res.get("error") else None
            total = int(q["marks"])
            try:
                awarded_f = float(awarded) if awarded is not None else 0.0
            except (TypeError, ValueError):
                awarded_f = 0.0
            db.insert_attempt(
                question_id=item.question_id,
                student_answer=item.answer,
                marks_awarded=awarded_f if awarded is not None else None,
                marks_total=total,
                marking_response_json=json.dumps(res, ensure_ascii=False),
                attempted_at=attempted_at,
                exam_session_id=payload.session_id,
                user_id=user["id"] if user else None,
            )
            total_possible += total
            total_awarded += awarded_f if awarded is not None else 0.0
            per_question.append(
                {
                    "question_id": item.question_id,
                    "marks_awarded": awarded,
                    "marks_total": total,
                    "result": res,
                    "flagged": item.flagged,
                }
            )

        finished_at = datetime.now(timezone.utc).isoformat()
        db.finalize_exam_session(
            payload.session_id,
            finished_at=finished_at,
            total_marks_awarded=total_awarded,
            total_marks_possible=total_possible,
        )
        return JSONResponse(
            {
                "session_id": payload.session_id,
                "total_awarded": total_awarded,
                "total_possible": total_possible,
                "percentage": round(100.0 * total_awarded / total_possible, 1) if total_possible else 0.0,
                "per_question": per_question,
            }
        )

    @app.get("/exam-sim/results/{session_id}")
    async def exam_results(session_id: int, request: Request):
        session = db.get_exam_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Exam session not found")
        attempts = db.get_session_attempts(session_id)
        question_ids = [a["question_id"] for a in attempts]
        qmap = {q["id"]: q for q in db.get_questions_by_ids(question_ids)}
        rows = []
        for a in attempts:
            q = qmap.get(a["question_id"]) or {}
            try:
                marking = json.loads(a.get("marking_response_json") or "{}")
            except json.JSONDecodeError:
                marking = {}
            rows.append({"attempt": a, "question": q, "marking": marking})
        return templates.TemplateResponse(
            request,
            "exam_results.html",
            {
                "session": session,
                "rows": rows,
                "current_user": users.current_user(request),
            },
        )
