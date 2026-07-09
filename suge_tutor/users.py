"""User/session helpers.

Seeded local accounts retain personal grade targets (calculated externally).
SUGE is 50% of the course; the other 50% is coursework. Targets here are the
EXAM percentages required to land each grade given current coursework standing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Request

from .config import config

# Grade targets are the exam percentages each user needs to score, given their
# coursework standing, to achieve A5 / B3 / C3 overall.
LOCAL_USERS: dict[str, dict] = {
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
}

COOKIE_NAME = "suge_user"
SESSION_COOKIE_NAME = "suge_session"


def _db():
    from . import db

    return db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def current_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        user = _db().get_session_user(token, _now().isoformat())
        if user:
            return user
    uid = request.cookies.get(COOKIE_NAME)
    if uid:
        if config.ALLOW_LOCAL_USER_PICKER:
            return _db().get_user(uid.lower()) or LOCAL_USERS.get(uid.lower())
    return None


def all_users() -> list[dict]:
    users = _db().list_users()
    return users or list(LOCAL_USERS.values())


def is_valid_user(uid: str) -> bool:
    return config.ALLOW_LOCAL_USER_PICKER and (_db().get_user(uid.lower()) is not None or uid.lower() in LOCAL_USERS)


def create_session(user_id: str) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    created = _now()
    expires = created + timedelta(days=365)
    _db().create_session(token, user_id, created.isoformat(), expires.isoformat())
    return token, expires


def delete_session(token: str | None) -> None:
    if token:
        _db().delete_session(token)


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 200_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 200_000).hex()
    return hmac.compare_digest(actual, digest)


def user_id_from_email(email: str) -> str:
    base = "".join(ch for ch in email.lower().split("@")[0] if ch.isalnum()) or "user"
    candidate = base[:24]
    if not _db().get_user(candidate):
        return candidate
    return f"{candidate}-{secrets.token_hex(3)}"


def encrypt_secret(value: str) -> str:
    key = hashlib.sha256(config.APP_SECRET_KEY.encode("utf-8")).digest()
    data = value.encode("utf-8")
    out = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.urlsafe_b64encode(out).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    key = hashlib.sha256(config.APP_SECRET_KEY.encode("utf-8")).digest()
    try:
        data = base64.urlsafe_b64decode(value.encode("ascii"))
    except Exception:
        return None
    out = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return out.decode("utf-8", errors="ignore")


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
