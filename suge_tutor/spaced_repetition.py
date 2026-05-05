"""Spaced-repetition scheduling, with awareness of the exam date.

Default cadence (well before exam): easy=+7 d (×2 ease growth, capped 90 d),
needs=+2 d, hard=+1 d.

As the exam approaches, intervals compress so every rating still recycles the
question through at least once before exam day. No interval is allowed to
schedule the next review past the exam date itself.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .config import config

EASY = "easy"
NEEDS = "needs"
HARD = "hard"

VALID_RATINGS = {EASY, NEEDS, HARD}

BASE_INTERVAL_DAYS = {EASY: 7, NEEDS: 2, HARD: 1}
MAX_INTERVAL_DAYS = 90


def _exam_date() -> date | None:
    raw = (config.EXAM_DATE or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def days_to_exam(today: date | None = None) -> int | None:
    """Whole days until the exam date. None if no exam configured. Negative if past."""
    exam = _exam_date()
    if exam is None:
        return None
    today = today or datetime.now(timezone.utc).date()
    return (exam - today).days


def _runway_cap(rating: str, days_left: int) -> int:
    """How many days a rating may push a review out, given the runway.

    With days_left=10 (typical exam-week start) we want easy≈5d, needs≈2d, hard=1d.
    With days_left≤2 everything collapses to 1d.
    """
    if days_left <= 1:
        return 1
    if rating == EASY:
        # ~half the runway, but never more than 7 days
        return max(1, min(7, days_left // 2))
    if rating == NEEDS:
        return max(1, min(2, days_left // 4)) or 1
    # HARD always next day
    return 1


def schedule(rating: str, prev_ease: int, *, today: date | None = None) -> tuple[datetime, int]:
    """Return (next_review_at, new_ease_level)."""
    if rating not in VALID_RATINGS:
        raise ValueError(f"unknown rating: {rating}")
    now = datetime.now(timezone.utc)

    base = BASE_INTERVAL_DAYS[rating]
    if rating == EASY:
        new_ease = prev_ease + 1
        days = min(base * (2 ** prev_ease), MAX_INTERVAL_DAYS)
    elif rating == HARD:
        new_ease = max(0, prev_ease - 1)
        days = base
    else:
        new_ease = prev_ease
        days = base

    # Compress intervals if we're close to the exam.
    days_left = days_to_exam(today=today or now.date())
    if days_left is not None and days_left > 0:
        runway = _runway_cap(rating, days_left)
        days = min(days, runway)
        # Hard cap: next review must land on or before exam day itself.
        days = max(1, min(days, days_left))

    return now + timedelta(days=days), new_ease
