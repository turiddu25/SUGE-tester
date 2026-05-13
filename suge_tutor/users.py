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
    "fraser": {
        "id": "fraser",
        "name": "Fraser",
        # Placeholder targets — same defaults as Salvo. Update once Fraser's
        # coursework standing is known so the dashboard A5/B3/C3 thresholds
        # reflect the percentages he actually needs in the exam.
        "grade_targets": {"A5": 53, "B3": 33, "C3": 13},
    },
    "dickson": {
        "id": "dickson",
        "name": "Dickson",
        # Placeholder targets — same defaults as Salvo. Update once Dickson's
        # coursework standing is known.
        "grade_targets": {"A5": 53, "B3": 33, "C3": 13},
    },
    "guest": {
        "id": "guest",
        "name": "Guest",
        # No personalised grade targets — the targets card on the dashboard
        # hides when grade_targets is empty (see home.html:34). Guest mode
        # is for browsing the bank without committing per-user attempt data
        # to a named account; attempts still get tagged user_id="guest".
        "grade_targets": {},
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
