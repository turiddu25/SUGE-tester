from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates

from .. import db, users
from ..products import get_product, list_products


def register(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.get("/cribsheet")
    async def cribsheet_index(request: Request):
        """Landing page for cribsheet drills — 4 product cards.
        Each card pulls its question count from `questions` table filtered by
        product_id. Cards link to /cribsheet/{product_id}."""
        cards = []
        for p in list_products():
            cards.append({
                **p,
                "question_count": db.question_count_by_product(p["id"]),
            })
        return templates.TemplateResponse(
            request,
            "cribsheet.html",
            {
                "cards": cards,
                "current_user": users.current_user(request),
            },
        )

    @app.get("/cribsheet/{product_id}")
    async def cribsheet_product(product_id: str, request: Request):
        """List the 8 cribsheet questions for one product, with a 'practice'
        link to the standard /practice/{id} flow for each."""
        prod = get_product(product_id)
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")
        questions = db.list_questions(
            source="cribsheet_products",
            product_id=product_id,
        )
        return templates.TemplateResponse(
            request,
            "cribsheet_product.html",
            {
                "product": prod,
                "questions": questions,
                "current_user": users.current_user(request),
            },
        )
