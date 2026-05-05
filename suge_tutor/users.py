"""Tiny local accounts. No auth — the user picks Salvo or Aryan from a screen."""

from __future__ import annotations

from fastapi import Request

USERS: dict[str, dict[str, str]] = {
    "salvo": {"id": "salvo", "name": "Salvo"},
    "aryan": {"id": "aryan", "name": "Aryan"},
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
