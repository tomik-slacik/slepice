import datetime as dt
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..tick import compute_streak, compute_week_balance, effective_today_for_hen, run_tick_for_hen

router = APIRouter(prefix="/hens", tags=["hens"])


def _get_owned_hen(hen_id: int, current_user: models.User, db: Session) -> models.Hen:
    hen = db.get(models.Hen, hen_id)
    if hen is None:
        raise HTTPException(404, "hen not found")
    if hen.user_id != current_user.id:
        # 404, not 403 - don't reveal that a hen with this id exists at all
        raise HTTPException(404, "hen not found")
    return hen


@router.post("", response_model=schemas.HenOut, status_code=201)
def adopt_hen(
    payload: schemas.HenCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = db.query(models.Farm).filter(models.Farm.key == payload.farm_key).first()
    if farm is None:
        raise HTTPException(404, f"unknown farm_key '{payload.farm_key}'")
    if farm.weekly_capacity is not None and len(farm.hens) >= farm.weekly_capacity:
        raise HTTPException(409, f"'{farm.name}' has no free capacity this week - try another farm")

    hen = models.Hen(
        user_id=current_user.id,
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


@router.get("", response_model=List[schemas.HenOut])
def list_my_hens(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Hen).filter(models.Hen.user_id == current_user.id).all()


@router.get("/{hen_id}", response_model=schemas.HenOut)
def get_hen(hen_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_owned_hen(hen_id, current_user, db)


@router.patch("/{hen_id}", response_model=schemas.HenOut)
def update_hen(
    hen_id: int,
    payload: schemas.HenUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hen = _get_owned_hen(hen_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(hen, field, value)
    db.commit()
    db.refresh(hen)
    return hen


@router.delete("/{hen_id}", status_code=204)
def cancel_hen(hen_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cancels the subscription outright - a hard delete, not a "paused"
    flag flip (that already exists via PATCH .../paused). Cascades to the
    hen's feed log, deliveries and paused-day records (see the
    cascade="all, delete-orphan" relationships on Hen in models.py) - there
    is no separate wallet ledger to refund here, since Kvoč never holds a
    real prepaid balance (see docs/PAYMENT_INTEGRATION.md).
    """
    hen = _get_owned_hen(hen_id, current_user, db)
    db.delete(hen)
    db.commit()


@router.get("/{hen_id}/wallet", response_model=schemas.WalletOut)
def get_wallet(hen_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    hen = _get_owned_hen(hen_id, current_user, db)
    today = effective_today_for_hen(db, hen)
    return schemas.WalletOut(
        daily_amount=hen.daily_amount,
        week_balance=compute_week_balance(db, hen, today),
        streak=compute_streak(db, hen, today),
    )


@router.get("/{hen_id}/feed-log", response_model=List[schemas.FeedLogEntryOut])
def get_feed_log(hen_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    hen = _get_owned_hen(hen_id, current_user, db)
    return list(reversed(hen.feed_log))


@router.get("/{hen_id}/deliveries", response_model=List[schemas.DeliveryOut])
def get_deliveries(hen_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    hen = _get_owned_hen(hen_id, current_user, db)
    return list(reversed(hen.deliveries))
