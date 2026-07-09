from __future__ import annotations

from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import db, users
from ..config import config


def register(app: FastAPI, templates: Jinja2Templates) -> None:
    def _auth_url(path: str, next_url: str, **params: str) -> str:
        query = f"next={quote(users.safe_next_url(next_url), safe='')}"
        for key, value in params.items():
            query += f"&{key}={quote(value, safe='')}"
        return f"{path}?{query}"

    @app.get("/users")
    async def picker(request: Request):
        if config.ALLOW_LOCAL_USER_PICKER:
            return templates.TemplateResponse(
                request,
                "user_picker.html",
                {
                    "users_": users.all_users(),
                    "current": users.current_user(request),
                    "current_user": users.current_user(request),
                    "next_url": users.safe_next_url(request.query_params.get("next")),
                    "allow_local_picker": config.ALLOW_LOCAL_USER_PICKER,
                },
            )
        return RedirectResponse(url=_auth_url("/login", users.safe_next_url(request.query_params.get("next"))), status_code=303)

    @app.get("/login")
    async def login_page(request: Request):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "current_user": users.current_user(request),
                "next_url": users.safe_next_url(request.query_params.get("next")),
                "error": request.query_params.get("error") == "1",
            },
        )

    @app.get("/register")
    async def register_page(request: Request):
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "current_user": users.current_user(request),
                "next_url": users.safe_next_url(request.query_params.get("next")),
                "error": request.query_params.get("error") or "",
                "min_password_length": users.MIN_PASSWORD_LENGTH,
            },
        )

    @app.post("/users/switch/{uid}")
    async def switch_user(uid: str, request: Request):
        if not users.is_valid_user(uid):
            raise HTTPException(status_code=404, detail="Unknown user")
        form = await request.form()
        next_url = users.safe_next_url(str(form.get("next") or request.query_params.get("next") or "/"))
        resp = RedirectResponse(url=next_url, status_code=303)
        # Long-lived cookie — this is a single-machine app and the user explicitly picked.
        resp.set_cookie(
            users.COOKIE_NAME,
            uid.lower(),
            max_age=60 * 60 * 24 * 365,
            httponly=False,
            samesite="lax",
            secure=users.secure_cookie(request),
        )
        return resp

    @app.post("/users/register")
    async def register_user(request: Request):
        form = await request.form()
        name = str(form.get("name") or "").strip()
        email = str(form.get("email") or "").strip().lower()
        password = str(form.get("password") or "")
        next_url = users.safe_next_url(str(form.get("next") or "/"))
        if not name or not email or len(password) < users.MIN_PASSWORD_LENGTH:
            return RedirectResponse(url=_auth_url("/register", next_url, error="weak"), status_code=303)
        if db.get_user_by_email(email):
            return RedirectResponse(url=_auth_url("/register", next_url, error="invalid"), status_code=303)
        user = db.create_user(
            user_id=users.user_id_from_email(email),
            name=name,
            email=email,
            password_hash=users.password_hash(password),
            grade_targets={"A5": 53, "B3": 33, "C3": 13},
        )
        token, expires = users.create_session(user["id"])
        resp = RedirectResponse(url=next_url, status_code=303)
        resp.set_cookie(users.SESSION_COOKIE_NAME, token, expires=expires, httponly=True, samesite="lax", secure=users.secure_cookie(request))
        resp.delete_cookie(users.COOKIE_NAME)
        return resp

    @app.post("/users/login")
    async def login_user(request: Request):
        form = await request.form()
        email = str(form.get("email") or "").strip().lower()
        password = str(form.get("password") or "")
        next_url = users.safe_next_url(str(form.get("next") or "/"))
        user = db.get_user_by_email(email)
        if not user or not users.verify_password(password, user.get("password_hash")):
            return RedirectResponse(url=_auth_url("/login", next_url, error="1"), status_code=303)
        token, expires = users.create_session(user["id"])
        resp = RedirectResponse(url=next_url, status_code=303)
        resp.set_cookie(users.SESSION_COOKIE_NAME, token, expires=expires, httponly=True, samesite="lax", secure=users.secure_cookie(request))
        resp.delete_cookie(users.COOKIE_NAME)
        return resp

    @app.get("/settings")
    async def settings(request: Request):
        user = users.current_user(request)
        if not user:
            return RedirectResponse(url="/login?next=/settings", status_code=303)
        settings = db.ensure_user_settings(user["id"])
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "current_user": user,
                "settings": settings,
                "has_own_key": bool(settings.get("encrypted_llm_api_key")),
                "default_budget": config.DEFAULT_MONTHLY_LLM_BUDGET_GBP,
            },
        )

    @app.post("/settings")
    async def save_settings(
        request: Request,
        exam_year: str = Form("2025-26"),
        llm_provider: str = Form(""),
        llm_base_url: str = Form(""),
        llm_model: str = Form(""),
        llm_api_key: str = Form(""),
        monthly_budget_gbp: str = Form(""),
        use_own_key: str | None = Form(None),
    ):
        user = users.current_user(request)
        if not user:
            return RedirectResponse(url="/login?next=/settings", status_code=303)
        encrypted = users.encrypt_secret(llm_api_key.strip()) if llm_api_key.strip() else None
        try:
            budget = float(monthly_budget_gbp) if monthly_budget_gbp.strip() else None
        except ValueError:
            budget = config.DEFAULT_MONTHLY_LLM_BUDGET_GBP
        db.update_user_settings(
            user["id"],
            exam_year=exam_year.strip() or "2025-26",
            llm_provider=llm_provider.strip() or None,
            llm_base_url=llm_base_url.strip() or None,
            llm_model=llm_model.strip() or None,
            encrypted_llm_api_key=encrypted,
            monthly_budget_gbp=budget,
            use_own_key=bool(use_own_key),
        )
        return RedirectResponse(url="/settings?saved=1", status_code=303)

    @app.post("/users/logout")
    async def logout(request: Request):
        users.delete_session(request.cookies.get(users.SESSION_COOKIE_NAME))
        resp = RedirectResponse(url="/", status_code=303)
        resp.delete_cookie(users.COOKIE_NAME)
        resp.delete_cookie(users.SESSION_COOKIE_NAME)
        return resp
