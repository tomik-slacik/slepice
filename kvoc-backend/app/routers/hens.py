import datetime as dt
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..tick import compute_streak, compute_week_balance, run_tick_for_hen

router = APIRouter(prefix="/hens", tags=["hens"])


@router.post("", response_model=schemas.HenOut, status_code=201)
def adopt_hen(payload: schemas.HenCreate, db: Session = Depends(get_db)):
    """Adopting a hen = signing up. There's no auth yet (see README), so
    owner_name is just a free-text label for now.
    """
    farm = db.query(models.Farm).filter(models.Farm.key == payload.farm_key).first()
    if farm is None:
        raise HTTPException(404, f"unknown farm_key '{payload.farm_key}'")

    hen = models.Hen(
        owner_name=payload.owner_name,
        hen_name=payload.hen_name,
        farm_id=farm.id,
        daily_amount=payload.daily_amount,
        address=payload.address,
    )
    db.add(hen)
    db.commit()
    db.refresh(hen)

    # run day one immediately, same as the frontend demo does right after onboarding,
    # so the hen doesn't sit empty until tomorrow's scheduled tick
    run_tick_for_hen(db, hen, dt.date.today())
    db.refresh(hen)
    return hen


@router.get("/{hen_id}", response_model=schemas.HenOut)
def get_hen(hen_id: int, db: Session = Depends(get_db)):
    hen = db.get(models.Hen, hen_id)
    if hen is None:
        raise HTTPException(404, "hen not found")
    return hen


@router.patch("/{hen_id}", response_model=schemas.HenOut)
def update_hen(hen_id: int, payload: schemas.HenUpdate, db: Session = Depends(get_db)):
    hen = db.get(models.Hen, hen_id)
    if hen is None:
        raise HTTPException(404, "hen not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(hen, field, value)
    db.commit()
    db.refresh(hen)
    return hen


@router.get("/{hen_id}/wallet", response_model=schemas.WalletOut)
def get_wallet(hen_id: int, db: Session = Depends(get_db)):
    hen = db.get(models.Hen, hen_id)
    if hen is None:
        raise HTTPException(404, "hen not found")
    return schemas.WalletOut(
        daily_amount=hen.daily_amount,
        week_balance=compute_week_balance(db, hen),
        streak=compute_streak(db, hen),
    )


@router.get("/{hen_id}/feed-log", response_model=List[schemas.FeedLogEntryOut])
def get_feed_log(hen_id: int, db: Session = Depends(get_db)):
    hen = db.get(models.Hen, hen_id)
    if hen is None:
        raise HTTPException(404, "hen not found")
    return list(reversed(hen.feed_log))


@router.get("/{hen_id}/deliveries", response_model=List[schemas.DeliveryOut])
def get_deliveries(hen_id: int, db: Session = Depends(get_db)):
    hen = db.get(models.Hen, hen_id)
    if hen is None:
        raise HTTPException(404, "hen not found")
    return list(reversed(hen.deliveries))
