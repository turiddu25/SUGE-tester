from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import users


def register(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.get("/users")
    async def picker(request: Request):
        return templates.TemplateResponse(
            request,
            "user_picker.html",
            {
                "users_": users.all_users(),
                "current": users.current_user(request),
                "next_url": request.query_params.get("next", "/"),
            },
        )

    @app.post("/users/switch/{uid}")
    async def switch_user(uid: str, request: Request):
        if not users.is_valid_user(uid):
            raise HTTPException(status_code=404, detail="Unknown user")
        form = await request.form()
        next_url = form.get("next") or request.query_params.get("next") or "/"
        # Keep redirects local to avoid open-redirect oddities.
        if not next_url.startswith("/"):
            next_url = "/"
        resp = RedirectResponse(url=next_url, status_code=303)
        # Long-lived cookie — this is a single-machine app and the user explicitly picked.
        resp.set_cookie(
            users.COOKIE_NAME,
            uid.lower(),
            max_age=60 * 60 * 24 * 365,
            httponly=False,
            samesite="lax",
        )
        return resp

    @app.post("/users/logout")
    async def logout(request: Request):
        resp = RedirectResponse(url="/users", status_code=303)
        resp.delete_cookie(users.COOKIE_NAME)
        return resp
