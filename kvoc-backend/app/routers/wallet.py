"""Wallet top-ups: the *real* payment, made in bulk (weekly/monthly), as
opposed to app/tick.py's daily entries which are just an internal ledger
draw-down against whatever was topped up here. See docs/PAYMENT_INTEGRATION.md.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import config, models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..integrations.payments import get_payment_provider
from .hens import _get_owned_hen

router = APIRouter(prefix="/hens/{hen_id}/wallet", tags=["wallet"])


@router.post("/setup-intent", response_model=schemas.SetupIntentOut)
def start_card_setup(
    hen_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 1 of saving a card: get a client_secret the frontend hands to
    Stripe.js (see app/static/card-setup.html) to actually collect card
    details. Card numbers never pass through this server.
    """
    _get_owned_hen(hen_id, current_user, db)  # 404s if not this user's hen
    provider = get_payment_provider()

    customer_id = provider.ensure_customer(current_user.id, current_user.email, current_user.stripe_customer_id)
    if customer_id != current_user.stripe_customer_id:
        current_user.stripe_customer_id = customer_id
        db.commit()

    intent = provider.create_setup_intent(customer_id)
    return schemas.SetupIntentOut(client_secret=intent.client_secret, publishable_key=intent.publishable_key)


@router.post("/topup", response_model=schemas.TopUpOut, status_code=201)
def top_up_wallet(
    hen_id: int,
    payload: schemas.TopUpCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 2: actually charge the saved card off-session. In production
    this is called by a recurring schedule (weekly/monthly), the same way
    app/scheduler.py drives the daily tick - not from the frontend on a
    button click, though this endpoint works fine for a manual top-up too.
    """
    hen = _get_owned_hen(hen_id, current_user, db)
    if not current_user.stripe_customer_id:
        raise HTTPException(400, "no saved payment method - call /setup-intent first")

    provider = get_payment_provider()
    result = provider.charge_saved_method(current_user.stripe_customer_id, payload.amount_czk)

    topup = models.WalletTopUp(
        hen_id=hen.id,
        amount_czk=payload.amount_czk,
        provider=config.PAYMENT_PROVIDER,
        provider_reference=result.provider_reference,
        status="succeeded" if result.success else "failed",
    )
    db.add(topup)
    db.commit()
    db.refresh(topup)

    if not result.success:
        raise HTTPException(402, f"payment failed: {result.message}")
    return topup


@router.get("/topups", response_model=list[schemas.TopUpOut])
def list_topups(
    hen_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hen = _get_owned_hen(hen_id, current_user, db)
    return (
        db.query(models.WalletTopUp)
        .filter(models.WalletTopUp.hen_id == hen.id)
        .order_by(models.WalletTopUp.created_at.desc())
        .all()
    )
