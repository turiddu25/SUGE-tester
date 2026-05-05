from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .. import db, users
from ..spaced_repetition import VALID_RATINGS, schedule


class ReviewRating(BaseModel):
    rating: str  # "easy" | "needs" | "hard"


def register(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.post("/api/review/{question_id}")
    async def rate(question_id: str, payload: ReviewRating, request: Request):
        if payload.rating not in VALID_RATINGS:
            raise HTTPException(status_code=400, detail="invalid rating")
        user = users.current_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="pick a user first")
        if not db.get_question(question_id):
            raise HTTPException(status_code=404, detail="question not found")

        existing = db.get_review(question_id, user["id"])
        prev_ease = int(existing["ease_level"]) if existing else 0
        next_at, new_ease = schedule(payload.rating, prev_ease)
        now = datetime.now(timezone.utc).isoformat()
        db.upsert_review(
            question_id=question_id,
            user_id=user["id"],
            next_review_at=next_at.isoformat(),
            ease_level=new_ease,
            rating=payload.rating,
            now=now,
        )
        return JSONResponse(
            {
                "ok": True,
                "next_review_at": next_at.isoformat(),
                "ease_level": new_ease,
                "rating": payload.rating,
            }
        )

    @app.get("/review")
    async def review_page(request: Request):
        user = users.current_user(request)
        now = datetime.now(timezone.utc).isoformat()
        due = db.due_reviews(user["id"], now) if user else []
        upcoming = db.upcoming_reviews(user["id"], limit=30) if user else []
        upcoming = [u for u in upcoming if u["next_review_at"] > now]
        return templates.TemplateResponse(
            request,
            "review.html",
            {
                "due": due,
                "upcoming": upcoming,
                "current_user": user,
            },
        )
