from __future__ import annotations

import datetime as dt
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from clinic_app.db import get_db
from clinic_app.deps import CurrentUser, forbid_demo_writes, get_current_user
from clinic_app.models import Patient, Visit


router = APIRouter(prefix="/patients")
templates = Jinja2Templates(directory="clinic_app/templates")


def _patient_or_404(db: Session, *, tenant_id: int, patient_id: int) -> Patient:
    patient = (
        db.query(Patient)
        .filter(Patient.tenant_id == tenant_id)
        .filter(Patient.id == patient_id)
        .first()
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("", response_class=HTMLResponse)
def list_patients(
    request: Request,
    q: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Patient).filter(Patient.tenant_id == user.tenant_id)
    if q and q.strip():
        s = f"%{q.strip()}%"
        query = query.filter(or_(Patient.name.ilike(s), Patient.phone.ilike(s), Patient.patient_code.ilike(s)))
    patients = query.order_by(Patient.created_at.desc()).limit(200).all()
    return templates.TemplateResponse(
        "patients_list.html",
        {"request": request, "user": user, "patients": patients, "q": q or ""},
    )


@router.get("/new", response_class=HTMLResponse)
def new_patient_page(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "patient_form.html",
        {"request": request, "user": user, "mode": "new", "patient": None},
    )


@router.post("/new")
def create_patient(
    request: Request,
    name: str = Form(...),
    phone: str | None = Form(default=None),
    email: str | None = Form(default=None),
    dob: str | None = Form(default=None),
    gender: str | None = Form(default=None),
    address: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    user: CurrentUser = Depends(forbid_demo_writes),
    db: Session = Depends(get_db),
):
    dob_date = None
    if dob:
        try:
            dob_date = dt.date.fromisoformat(dob)
        except ValueError:
            dob_date = None

    tmp_code = f"TMP-{secrets.token_hex(4)}"
    patient = Patient(
        tenant_id=user.tenant_id,
        patient_code=tmp_code,
        name=name.strip(),
        phone=(phone.strip() if phone else None),
        email=(email.strip() if email else None),
        dob=dob_date,
        gender=(gender.strip() if gender else None),
        address=(address.strip() if address else None),
        notes=(notes.strip() if notes else None),
    )
    db.add(patient)
    db.flush()  # assign ID
    patient.patient_code = f"P{patient.id:05d}"
    db.commit()
    return RedirectResponse(url=f"/patients/{patient.id}", status_code=302)


@router.get("/{patient_id}", response_class=HTMLResponse)
def patient_detail(
    request: Request,
    patient_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = _patient_or_404(db, tenant_id=user.tenant_id, patient_id=patient_id)
    visits = (
        db.query(Visit)
        .filter(Visit.tenant_id == user.tenant_id)
        .filter(Visit.patient_id == patient.id)
        .order_by(Visit.visit_date.desc(), Visit.id.desc())
        .all()
    )
    return templates.TemplateResponse(
        "patient_detail.html",
        {"request": request, "user": user, "patient": patient, "visits": visits},
    )


@router.get("/{patient_id}/edit", response_class=HTMLResponse)
def edit_patient_page(
    request: Request,
    patient_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = _patient_or_404(db, tenant_id=user.tenant_id, patient_id=patient_id)
    return templates.TemplateResponse(
        "patient_form.html",
        {"request": request, "user": user, "mode": "edit", "patient": patient},
    )


@router.post("/{patient_id}/edit")
def update_patient(
    patient_id: int,
    name: str = Form(...),
    phone: str | None = Form(default=None),
    email: str | None = Form(default=None),
    dob: str | None = Form(default=None),
    gender: str | None = Form(default=None),
    address: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    user: CurrentUser = Depends(forbid_demo_writes),
    db: Session = Depends(get_db),
):
    patient = _patient_or_404(db, tenant_id=user.tenant_id, patient_id=patient_id)
    dob_date = None
    if dob:
        try:
            dob_date = dt.date.fromisoformat(dob)
        except ValueError:
            dob_date = None

    patient.name = name.strip()
    patient.phone = phone.strip() if phone else None
    patient.email = email.strip() if email else None
    patient.dob = dob_date
    patient.gender = gender.strip() if gender else None
    patient.address = address.strip() if address else None
    patient.notes = notes.strip() if notes else None

    db.commit()
    return RedirectResponse(url=f"/patients/{patient.id}", status_code=302)


@router.post("/{patient_id}/delete")
def delete_patient(
    patient_id: int,
    user: CurrentUser = Depends(forbid_demo_writes),
    db: Session = Depends(get_db),
):
    patient = _patient_or_404(db, tenant_id=user.tenant_id, patient_id=patient_id)
    db.delete(patient)
    db.commit()
    return RedirectResponse(url="/patients", status_code=302)


@router.post("/{patient_id}/visits")
def add_visit(
    patient_id: int,
    visit_date: str | None = Form(default=None),
    complaints: str | None = Form(default=None),
    diagnosis: str | None = Form(default=None),
    treatment: str | None = Form(default=None),
    medicines: str | None = Form(default=None),
    user: CurrentUser = Depends(forbid_demo_writes),
    db: Session = Depends(get_db),
):
    patient = _patient_or_404(db, tenant_id=user.tenant_id, patient_id=patient_id)
    vdate = dt.date.today()
    if visit_date:
        try:
            vdate = dt.date.fromisoformat(visit_date)
        except ValueError:
            vdate = dt.date.today()

    visit = Visit(
        tenant_id=user.tenant_id,
        patient_id=patient.id,
        visit_date=vdate,
        complaints=(complaints.strip() if complaints else None),
        diagnosis=(diagnosis.strip() if diagnosis else None),
        treatment=(treatment.strip() if treatment else None),
        medicines=(medicines.strip() if medicines else None),
    )
    db.add(visit)
    db.commit()
    return RedirectResponse(url=f"/patients/{patient.id}", status_code=302)

