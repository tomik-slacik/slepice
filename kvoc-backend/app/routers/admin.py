"""Admin-only endpoints - real farm management and a basic operational
overview. Every route here requires require_admin (see auth.py): either the
KVOC_ADMIN_TOKEN shared header, or a logged-in user with is_admin=True.
Nothing here is reachable without one of those - see docs/ADMIN.md.
"""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_admin
from ..database import get_db
from ..tick import run_tick_for_all

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/run-tick")
def run_tick(days_offset: int = 0, db: Session = Depends(get_db)):
    """Manually run the daily tick, optionally pretending it's `days_offset`
    days in the future - the backend equivalent of the frontend demo's
    "Posunout o den" button, for seeing a full week without waiting.
    """
    fake_today = dt.date.today() + dt.timedelta(days=days_offset)
    count = run_tick_for_all(db, fake_today)
    return {"ran_for_hens": count, "as_of_date": fake_today.isoformat()}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_users = db.query(func.count(models.User.id)).scalar()
    total_hens = db.query(func.count(models.Hen.id)).scalar()
    active_hens = db.query(func.count(models.Hen.id)).filter(models.Hen.paused.is_(False)).scalar()
    revenue_total = (
        db.query(func.coalesce(func.sum(models.WalletTopUp.amount_czk), 0))
        .filter(models.WalletTopUp.status == "succeeded")
        .scalar()
    )
    failed_topups = db.query(func.count(models.WalletTopUp.id)).filter(models.WalletTopUp.status == "failed").scalar()
    return {
        "total_users": total_users,
        "total_hens": total_hens,
        "active_hens": active_hens,
        "paused_hens": total_hens - active_hens,
        "revenue_total_czk": revenue_total,
        "failed_topups": failed_topups,
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "created_at": u.created_at,
            "hen_count": len(u.hens),
            "has_saved_payment_method": bool(u.stripe_customer_id),
            "is_admin": u.is_admin,
        }
        for u in users
    ]


@router.get("/farms", response_model=list[schemas.FarmOut])
def list_farms_admin(db: Session = Depends(get_db)):
    out = []
    for f in db.query(models.Farm).all():
        row = schemas.FarmOut.model_validate(f)
        row.spots_left = f.weekly_capacity - len(f.hens) if f.weekly_capacity is not None else None
        out.append(row)
    return out


@router.post("/farms", response_model=schemas.FarmOut, status_code=201)
def create_farm(payload: schemas.FarmCreate, db: Session = Depends(get_db)):
    """Onboarding a real farm - see docs/LOGISTICS.md for what still has to
    happen outside this app before a farm added here is actually real
    (an actual agreement with an actual farmer)."""
    existing = db.query(models.Farm).filter(models.Farm.key == payload.key).first()
    if existing is not None:
        raise HTTPException(409, f"a farm with key '{payload.key}' already exists")
    farm = models.Farm(**payload.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    row = schemas.FarmOut.model_validate(farm)
    row.spots_left = farm.weekly_capacity  # brand new farm - nobody's adopted there yet
    return row


@router.patch("/farms/{key}", response_model=schemas.FarmOut)
def update_farm(key: str, payload: schemas.FarmUpdate, db: Session = Depends(get_db)):
    farm = db.query(models.Farm).filter(models.Farm.key == key).first()
    if farm is None:
        raise HTTPException(404, f"unknown farm key '{key}'")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(farm, field, value)
    db.commit()
    db.refresh(farm)
    row = schemas.FarmOut.model_validate(farm)
    row.spots_left = farm.weekly_capacity - len(farm.hens) if farm.weekly_capacity is not None else None
    return row
