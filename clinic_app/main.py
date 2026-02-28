from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from pathlib import Path

from clinic_app.db import Base, SessionLocal, engine, get_db
from clinic_app.deps import CurrentUser, get_current_user
from clinic_app.models import Bill, Patient, Product, Purchase, StockBatch
from clinic_app.billing import router as billing_router
from clinic_app.admin import router as admin_router
from clinic_app.inventory import router as inventory_router
from clinic_app.patients import router as patients_router
from clinic_app.purchases import router as purchases_router
from clinic_app.seed import ensure_seed
from clinic_app.settings import settings
from clinic_app.web import router as web_router


app = FastAPI(title="Clinic Management")
templates = Jinja2Templates(directory="clinic_app/templates")

app.mount("/static", StaticFiles(directory="clinic_app/static"), name="static")
app.include_router(web_router)
app.include_router(patients_router)
app.include_router(inventory_router)
app.include_router(purchases_router)
app.include_router(billing_router)
app.include_router(admin_router)


@app.exception_handler(StarletteHTTPException)
async def _http_exc_handler(request: Request, exc: StarletteHTTPException):
    accept = request.headers.get("accept", "")
    if exc.status_code == 401 and "text/html" in accept:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_seed(db)
    finally:
        db.close()


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/sidh.jpeg")
def sidha_background_image():
    # Serve the existing image from repo root for backgrounds.
    img_path = Path(__file__).resolve().parent.parent / "sidh.jpeg"
    return FileResponse(str(img_path), media_type="image/jpeg")


@dataclass
class DashboardMetrics:
    total_patients: int
    total_products: int
    total_stock_qty: int
    low_stock_products: int
    bills_30d: int
    revenue_30d: float
    purchases_30d: int
    spend_30d: float


@app.get("/dashboard")
def dashboard(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = dt.date.today()
    start = today - dt.timedelta(days=30)

    total_patients = (
        db.query(func.count(Patient.id))
        .filter(Patient.tenant_id == user.tenant_id)
        .scalar()
        or 0
    )

    stock_by_product = (
        db.query(
            StockBatch.product_id.label("product_id"),
            func.coalesce(func.sum(StockBatch.qty_on_hand), 0).label("qty"),
        )
        .filter(StockBatch.tenant_id == user.tenant_id)
        .group_by(StockBatch.product_id)
        .subquery()
    )
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
    total_stock_qty = (
        db.query(func.coalesce(func.sum(StockBatch.qty_on_hand), 0))
        .filter(StockBatch.tenant_id == user.tenant_id)
        .scalar()
        or 0
    )

    bills_30d = (
        db.query(func.count(Bill.id))
        .filter(Bill.tenant_id == user.tenant_id)
        .filter(Bill.bill_date >= start)
        .scalar()
        or 0
    )
    revenue_30d = (
        db.query(func.coalesce(func.sum(Bill.total), 0))
        .filter(Bill.tenant_id == user.tenant_id)
        .filter(Bill.bill_date >= start)
        .scalar()
        or 0
    )
    purchases_30d = (
        db.query(func.count(Purchase.id))
        .filter(Purchase.tenant_id == user.tenant_id)
        .filter(Purchase.invoice_date >= start)
        .scalar()
        or 0
    )
    spend_30d = (
        db.query(func.coalesce(func.sum(Purchase.total), 0))
        .filter(Purchase.tenant_id == user.tenant_id)
        .filter(Purchase.invoice_date >= start)
        .scalar()
        or 0
    )

    metrics = DashboardMetrics(
        total_patients=int(total_patients),
        total_products=int(total_products),
        total_stock_qty=int(total_stock_qty),
        low_stock_products=int(low_stock),
        bills_30d=int(bills_30d),
        revenue_30d=float(revenue_30d),
        purchases_30d=int(purchases_30d),
        spend_30d=float(spend_30d),
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "metrics": metrics,
            "app_env": settings.app_env,
        },
    )




