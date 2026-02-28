from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from clinic_app.db import get_db
from clinic_app.deps import CurrentUser, forbid_demo_writes, get_current_user
from clinic_app.models import Product, StockBatch


router = APIRouter(prefix="/inventory")
templates = Jinja2Templates(directory="clinic_app/templates")


def _product_or_404(db: Session, *, tenant_id: int, product_id: int) -> Product:
    product = (
        db.query(Product)
        .filter(Product.tenant_id == tenant_id)
        .filter(Product.id == product_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _product_stock_subq(db: Session, *, tenant_id: int):
    return (
        db.query(
            StockBatch.product_id.label("product_id"),
            func.coalesce(func.sum(StockBatch.qty_on_hand), 0).label("qty"),
        )
        .filter(StockBatch.tenant_id == tenant_id)
        .group_by(StockBatch.product_id)
        .subquery()
    )


@router.get("", response_class=HTMLResponse)
def inventory_home(
    request: Request,
    q: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stock_by_product = _product_stock_subq(db, tenant_id=user.tenant_id)
    query = (
        db.query(
            Product,
            func.coalesce(stock_by_product.c.qty, 0).label("qty"),
        )
        .outerjoin(stock_by_product, Product.id == stock_by_product.c.product_id)
        .filter(Product.tenant_id == user.tenant_id)
    )
    if q and q.strip():
        s = f"%{q.strip()}%"
        query = query.filter(or_(Product.name.ilike(s), Product.hsn_code.ilike(s)))

    rows = query.order_by(Product.created_at.desc()).limit(300).all()
    return templates.TemplateResponse(
        "inventory_list.html",
        {"request": request, "user": user, "rows": rows, "q": q or ""},
    )


@router.get("/metrics", response_class=HTMLResponse)
def inventory_metrics(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stock_by_product = _product_stock_subq(db, tenant_id=user.tenant_id)
    low_stock = (
        db.query(func.count(Product.id))
        .outerjoin(stock_by_product, Product.id == stock_by_product.c.product_id)
        .filter(Product.tenant_id == user.tenant_id)
        .filter(func.coalesce(stock_by_product.c.qty, 0) <= Product.reorder_level)
        .scalar()
        or 0
    )
    total_products = (
        db.query(func.count(Product.id))
        .filter(Product.tenant_id == user.tenant_id)
        .scalar()
        or 0
    )
    return templates.TemplateResponse(
        "inventory_metrics.html",
        {
            "request": request,
            "user": user,
            "low_stock": int(low_stock),
            "total_products": int(total_products),
            "now": dt.datetime.now(),
        },
    )


@router.get("/products/new", response_class=HTMLResponse)
def new_product_page(request: Request, user: CurrentUser = Depends(get_current_user)):
    return templates.TemplateResponse(
        "product_form.html",
        {"request": request, "user": user, "mode": "new", "product": None},
    )


@router.post("/products/new")
def create_product(
    name: str = Form(...),
    hsn_code: str | None = Form(default=None),
    gst_rate: str | None = Form(default=None),
    unit: str | None = Form(default="nos"),
    reorder_level: int = Form(default=10),
    user: CurrentUser = Depends(forbid_demo_writes),
    db: Session = Depends(get_db),
):
    try:
        gst = float(gst_rate) if gst_rate not in (None, "") else 0.0
    except ValueError:
        gst = 0.0

    product = Product(
        tenant_id=user.tenant_id,
        name=name.strip(),
        hsn_code=(hsn_code.strip() if hsn_code else None),
        gst_rate=gst,
        unit=(unit.strip() if unit else "nos"),
        reorder_level=int(reorder_level or 0),
    )
    db.add(product)
    db.commit()
    return RedirectResponse(url="/inventory", status_code=302)


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(
    request: Request,
    product_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = _product_or_404(db, tenant_id=user.tenant_id, product_id=product_id)
    batches = (
        db.query(StockBatch)
        .filter(StockBatch.tenant_id == user.tenant_id)
        .filter(StockBatch.product_id == product.id)
        .order_by(StockBatch.expiry_date.asc().nullslast(), StockBatch.id.asc())
        .all()
    )
    total_qty = sum(int(b.qty_on_hand or 0) for b in batches)
    return templates.TemplateResponse(
        "product_detail.html",
        {
            "request": request,
            "user": user,
            "product": product,
            "batches": batches,
            "total_qty": total_qty,
        },
    )


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
def edit_product_page(
    request: Request,
    product_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = _product_or_404(db, tenant_id=user.tenant_id, product_id=product_id)
    return templates.TemplateResponse(
        "product_form.html",
        {"request": request, "user": user, "mode": "edit", "product": product},
    )


@router.post("/products/{product_id}/edit")
def update_product(
    product_id: int,
    name: str = Form(...),
    hsn_code: str | None = Form(default=None),
    gst_rate: str | None = Form(default=None),
    unit: str | None = Form(default="nos"),
    reorder_level: int = Form(default=10),
    user: CurrentUser = Depends(forbid_demo_writes),
    db: Session = Depends(get_db),
):
    product = _product_or_404(db, tenant_id=user.tenant_id, product_id=product_id)
    try:
        gst = float(gst_rate) if gst_rate not in (None, "") else 0.0
    except ValueError:
        gst = 0.0

    product.name = name.strip()
    product.hsn_code = hsn_code.strip() if hsn_code else None
    product.gst_rate = gst
    product.unit = unit.strip() if unit else "nos"
    product.reorder_level = int(reorder_level or 0)
    db.commit()
    return RedirectResponse(url=f"/inventory/products/{product.id}", status_code=302)


@router.post("/products/{product_id}/delete")
def delete_product(
    product_id: int,
    user: CurrentUser = Depends(forbid_demo_writes),
    db: Session = Depends(get_db),
):
    product = _product_or_404(db, tenant_id=user.tenant_id, product_id=product_id)
    db.delete(product)
    db.commit()
    return RedirectResponse(url="/inventory", status_code=302)

