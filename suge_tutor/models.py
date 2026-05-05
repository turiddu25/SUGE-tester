from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MarkRequest(BaseModel):
    question_id: str
    student_answer: str
    duration_seconds: int | None = None
    exam_session_id: int | None = None


class ExamStartRequest(BaseModel):
    seed: int | None = None


class ExamSubmissionItem(BaseModel):
    question_id: str
    answer: str
    flagged: bool = False


class ExamSubmitRequest(BaseModel):
    session_id: int
    items: list[ExamSubmissionItem]
    duration_seconds: int | None = None


class MarkingResult(BaseModel):
    marks_awarded: float | None = None
    marks_total: int | None = None
    percentage: float | None = None
    points_awarded: list[dict[str, Any]] = []
    points_missed: list[dict[str, Any]] = []
    general_feedback: str | None = None
    exam_technique_notes: str | None = None
    would_pass_in_real_exam: bool | None = None
    raw_response: str | None = None
    error: str | None = None
