from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates

from .. import users
from ..products import get_product, list_products


def register(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.get("/products")
    async def products_index(request: Request):
        return templates.TemplateResponse(
            request,
            "products_index.html",
            {
                "products": list_products(),
                "current_user": users.current_user(request),
            },
        )

    @app.get("/products/{pid}")
    async def product_detail(pid: str, request: Request):
        prod = get_product(pid)
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")
        return templates.TemplateResponse(
            request,
            "product_detail.html",
            {
                "product": prod,
                "current_user": users.current_user(request),
            },
        )
