"""Simple spaced-repetition scheduling.

Per the spec (section 5.2):
  - "Got it"      → +7 days, ease grows so each successful review extends ×2
  - "Needs review"→ +2 days, ease unchanged
  - "Hard"        → +1 day, ease decremented (toward 0)

`ease_level` is the count of consecutive successful "easy" ratings; each adds a ×2
multiplier on top of the base 7-day interval, capped at 90 days so things don't
escape the queue forever.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

EASY = "easy"
NEEDS = "needs"
HARD = "hard"

VALID_RATINGS = {EASY, NEEDS, HARD}

BASE_INTERVAL_DAYS = {EASY: 7, NEEDS: 2, HARD: 1}
MAX_INTERVAL_DAYS = 90


def schedule(rating: str, prev_ease: int) -> tuple[datetime, int]:
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
    return now + timedelta(days=days), new_ease
