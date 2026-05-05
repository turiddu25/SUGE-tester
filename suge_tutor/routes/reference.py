from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from .. import users
from ..reference import CHUNKS, KEY_FORMULAS


def register(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.get("/reference")
    async def reference_page(request: Request):
        return templates.TemplateResponse(
            request,
            "reference.html",
            {
                "chunks": CHUNKS,
                "formulas": KEY_FORMULAS,
                "current_user": users.current_user(request),
            },
        )
