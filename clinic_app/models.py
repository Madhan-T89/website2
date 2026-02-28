from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clinic_app.db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uq_user_tenant_username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)

    username: Mapped[str] = mapped_column(String(60))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="staff")  # admin|staff|demo
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=func.now())

    tenant: Mapped["Tenant"] = relationship(backref="users")


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("tenant_id", "patient_code", name="uq_patient_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)

    patient_code: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    dob: Mapped[Optional[dt.date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    visits: Mapped[list["Visit"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)

    visit_date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today, index=True)
    complaints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medicines: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # freeform / newline list

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=func.now())

    patient: Mapped["Patient"] = relationship(back_populates="visits")


class Vendor(Base):
    __tablename__ = "vendors"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_vendor_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)

    name: Mapped[str] = mapped_column(String(140))
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=func.now())


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_product_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)

    name: Mapped[str] = mapped_column(String(160), index=True)
    hsn_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    gst_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    unit: Mapped[str] = mapped_column(String(20), default="nos")
    reorder_level: Mapped[int] = mapped_column(Integer, default=10)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=func.now())

    batches: Mapped[list["StockBatch"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class StockBatch(Base):
    __tablename__ = "stock_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "batch_no", name="uq_batch_product"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)

    batch_no: Mapped[str] = mapped_column(String(60))
    expiry_date: Mapped[Optional[dt.date]] = mapped_column(Date, nullable=True, index=True)
    qty_on_hand: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=func.now())

    product: Mapped["Product"] = relationship(back_populates="batches")


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (UniqueConstraint("tenant_id", "invoice_no", name="uq_purchase_invoice"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)

    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    invoice_no: Mapped[str] = mapped_column(String(60))
    invoice_date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today, index=True)

    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    gst_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=func.now())

    vendor: Mapped["Vendor"] = relationship()
    items: Mapped[list["PurchaseItem"]] = relationship(back_populates="purchase", cascade="all, delete-orphan")


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)

    batch_no: Mapped[str] = mapped_column(String(60))
    expiry_date: Mapped[Optional[dt.date]] = mapped_column(Date, nullable=True)

    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    gst_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)

    gst_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    purchase: Mapped["Purchase"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (UniqueConstraint("tenant_id", "bill_no", name="uq_bill_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)

    bill_no: Mapped[str] = mapped_column(String(60), index=True)
    bill_date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today, index=True)

    consulting_fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    gst_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    clinic_name: Mapped[str] = mapped_column(String(200))
    clinic_phone: Mapped[str] = mapped_column(String(60), default="")
    clinic_address: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=func.now())

    patient: Mapped["Patient"] = relationship()
    lines: Mapped[list["BillLine"]] = relationship(back_populates="bill", cascade="all, delete-orphan")


class BillLine(Base):
    __tablename__ = "bill_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)

    line_type: Mapped[str] = mapped_column(String(30))  # consulting|treatment|medicine
    description: Mapped[str] = mapped_column(String(240))
    qty: Mapped[float] = mapped_column(Numeric(12, 3), default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    gst_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)

    gst_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    bill: Mapped["Bill"] = relationship(back_populates="lines")
    product: Mapped[Optional["Product"]] = relationship()

