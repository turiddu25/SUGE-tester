"""Tiny local accounts. No auth — the user picks Salvo or Aryan from a screen.

Each user also has personal grade targets (calculated externally — see below).
SUGE is 50% of the course; the other 50% is coursework. Targets here are the
EXAM percentages required to land each grade given current coursework standing.
"""

from __future__ import annotations

from fastapi import Request

# Grade targets are the exam percentages each user needs to score, given their
# coursework standing, to achieve A5 / B3 / C3 overall.
USERS: dict[str, dict] = {
    "salvo": {
        "id": "salvo",
        "name": "Salvo",
        "grade_targets": {"A5": 53, "B3": 33, "C3": 13},
    },
    "aryan": {
        "id": "aryan",
        "name": "Aryan",
        "grade_targets": {"A5": 56, "B3": 36, "C3": 16},
    },
}

COOKIE_NAME = "suge_user"


def current_user(request: Request) -> dict | None:
    uid = request.cookies.get(COOKIE_NAME)
    if not uid:
        return None
    return USERS.get(uid.lower())


def all_users() -> list[dict]:
    return list(USERS.values())


def is_valid_user(uid: str) -> bool:
    return uid.lower() in USERS


def grade_for(percentage: float | None, targets: dict[str, int]) -> dict:
    """Given an exam percentage and a user's targets, return:

    {achieved: 'A5'|'B3'|'C3'|None, next: ('A5', gap_pct)|None}

    `achieved` is the highest grade whose threshold is met.
    `next` is the next grade up plus how many percentage points away you are.
    """
    if percentage is None:
        return {"achieved": None, "next": None}
    sorted_grades = sorted(targets.items(), key=lambda kv: -kv[1])  # high → low
    achieved = None
    for name, threshold in sorted_grades:
        if percentage >= threshold:
            achieved = name
            break
    next_grade = None
    for name, threshold in reversed(sorted_grades):  # low → high
        if percentage < threshold:
            next_grade = (name, round(threshold - percentage, 1))
            break
    return {"achieved": achieved, "next": next_grade}
