from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from clinic_app.db import get_db
from clinic_app.deps import CurrentUser, forbid_demo_writes, get_current_user
from clinic_app.models import Product, Purchase, PurchaseItem, StockBatch, Vendor


router = APIRouter(prefix="/purchases")
templates = Jinja2Templates(directory="clinic_app/templates")


def _d(x: str | None, default: Decimal = Decimal("0")) -> Decimal:
    if x is None:
        return default
    s = str(x).strip()
    if s == "":
        return default
    try:
        return Decimal(s)
    except InvalidOperation:
        return default


@router.get("", response_class=HTMLResponse)
def purchases_list(
    request: Request,
    q: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Purchase).filter(Purchase.tenant_id == user.tenant_id)
    if q and q.strip():
        s = f"%{q.strip()}%"
        query = query.join(Vendor, Vendor.id == Purchase.vendor_id).filter(
            or_(Purchase.invoice_no.ilike(s), Vendor.name.ilike(s))
        )
    purchases = query.order_by(Purchase.invoice_date.desc(), Purchase.id.desc()).limit(200).all()
    return templates.TemplateResponse(
        "purchases_list.html",
        {"request": request, "user": user, "purchases": purchases, "q": q or ""},
    )


@router.get("/new", response_class=HTMLResponse)
def new_purchase_page(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    products = (
        db.query(Product)
        .filter(Product.tenant_id == user.tenant_id)
        .order_by(Product.name.asc())
        .all()
    )
    return templates.TemplateResponse(
        "purchase_form.html",
        {"request": request, "user": user, "products": products, "today": dt.date.today()},
    )


@router.post("/new")
def create_purchase(
    vendor_name: str = Form(...),
    invoice_no: str = Form(...),
    invoice_date: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    product_id: list[int] = Form(default=[]),
    batch_no: list[str] = Form(default=[]),
    expiry_date: list[str] = Form(default=[]),
    qty: list[int] = Form(default=[]),
    unit_price: list[str] = Form(default=[]),
    gst_rate: list[str] = Form(default=[]),
    user: CurrentUser = Depends(forbid_demo_writes),
    db: Session = Depends(get_db),
):
    inv_date = dt.date.today()
    if invoice_date:
        try:
            inv_date = dt.date.fromisoformat(invoice_date)
        except ValueError:
            inv_date = dt.date.today()

    vname = vendor_name.strip()
    vendor = (
        db.query(Vendor)
        .filter(Vendor.tenant_id == user.tenant_id)
        .filter(Vendor.name == vname)
        .first()
    )
    if vendor is None:
        vendor = Vendor(tenant_id=user.tenant_id, name=vname)
        db.add(vendor)
        db.flush()

    purchase = Purchase(
        tenant_id=user.tenant_id,
        vendor_id=vendor.id,
        invoice_no=invoice_no.strip(),
        invoice_date=inv_date,
        notes=(notes.strip() if notes else None),
        subtotal=0,
        gst_total=0,
        total=0,
    )
    db.add(purchase)
    db.flush()

    subtotal = Decimal("0")
    gst_total_d = Decimal("0")
    total_d = Decimal("0")

    n = min(len(product_id), len(batch_no), len(qty), len(unit_price), len(gst_rate), len(expiry_date))
    for i in range(n):
        pid = int(product_id[i])
        bno = str(batch_no[i]).strip()
        if not bno or qty[i] is None:
            continue

        q_i = int(qty[i])
        if q_i <= 0:
            continue

        up = _d(unit_price[i])
        gstp = _d(gst_rate[i])
        line_sub = (Decimal(q_i) * up).quantize(Decimal("0.01"))
        line_gst = (line_sub * gstp / Decimal("100")).quantize(Decimal("0.01"))
        line_total = (line_sub + line_gst).quantize(Decimal("0.01"))

        exp = None
        if expiry_date[i]:
            try:
                exp = dt.date.fromisoformat(expiry_date[i])
            except ValueError:
                exp = None

        item = PurchaseItem(
            purchase_id=purchase.id,
            tenant_id=user.tenant_id,
            product_id=pid,
            batch_no=bno,
            expiry_date=exp,
            qty=q_i,
            unit_price=float(up),
            gst_rate=float(gstp),
            gst_amount=float(line_gst),
            line_total=float(line_total),
        )
        db.add(item)

        # Upsert stock batch and increment qty_on_hand.
        sb = (
            db.query(StockBatch)
            .filter(StockBatch.tenant_id == user.tenant_id)
            .filter(StockBatch.product_id == pid)
            .filter(StockBatch.batch_no == bno)
            .first()
        )
        if sb is None:
            sb = StockBatch(
                tenant_id=user.tenant_id,
                product_id=pid,
                batch_no=bno,
                expiry_date=exp,
                qty_on_hand=q_i,
            )
            db.add(sb)
        else:
            sb.qty_on_hand = int(sb.qty_on_hand or 0) + q_i
            if exp and (sb.expiry_date is None or exp != sb.expiry_date):
                sb.expiry_date = exp

        subtotal += line_sub
        gst_total_d += line_gst
        total_d += line_total

    purchase.subtotal = float(subtotal)
    purchase.gst_total = float(gst_total_d)
    purchase.total = float(total_d)

    db.commit()
    return RedirectResponse(url="/purchases", status_code=302)

