"""Wallet top-ups for the other-livestock side (goat/sheep/cow - see
docs/LIVESTOCK.md) - the animal-shaped twin of routers/wallet.py. Was the
one honestly-documented gap left there ("Animal nema vlastni platebni tok"):
adopting an animal and running the daily tick worked, but nothing actually
charged real money for it. Same split as the hen side: this file charges,
app/tick.py only ever draws down against what's charged here. See that
file's own module docstring for the *why* behind the split - not repeated
here since it's identical.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import config, models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..integrations.notifications import get_notification_provider
from ..integrations.payments import get_payment_provider
from .animals import _get_owned_animal

router = APIRouter(prefix="/animals/{animal_id}/wallet", tags=["animal-wallet"])


@router.post("/setup-intent", response_model=schemas.SetupIntentOut)
def start_animal_card_setup(
    animal_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Same saved-card flow as POST /hens/{hen_id}/wallet/setup-intent -
    genuinely the same step, not a duplicate: the saved payment method
    belongs to the *user* (current_user.stripe_customer_id), not to any one
    hen or animal, so either endpoint reaches the same place. This one
    exists so an account with only animals (no hen at all) has a route to
    it too - without it, such an account would have no hen_id to call the
    hens/ version on.
    """
    _get_owned_animal(animal_id, current_user, db)  # 404s if not this user's animal
    provider = get_payment_provider()

    customer_id = provider.ensure_customer(current_user.id, current_user.email, current_user.stripe_customer_id)
    if customer_id != current_user.stripe_customer_id:
        current_user.stripe_customer_id = customer_id
        db.commit()

    intent = provider.create_setup_intent(customer_id)
    return schemas.SetupIntentOut(client_secret=intent.client_secret, publishable_key=intent.publishable_key)


@router.post("/topup", response_model=schemas.TopUpOut, status_code=201)
def top_up_animal_wallet(
    animal_id: int,
    payload: schemas.TopUpCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    animal = _get_owned_animal(animal_id, current_user, db)
    if not current_user.stripe_customer_id:
        raise HTTPException(400, "no saved payment method - call /setup-intent first")

    provider = get_payment_provider()
    result = provider.charge_saved_method(current_user.stripe_customer_id, payload.amount_czk)

    topup = models.AnimalWalletTopUp(
        animal_id=animal.id,
        amount_czk=payload.amount_czk,
        provider=config.PAYMENT_PROVIDER,
        provider_reference=result.provider_reference,
        status="succeeded" if result.success else "failed",
    )
    db.add(topup)

    notifier = get_notification_provider()
    display_name = animal.name or animal.species
    if result.success:
        if animal.paused and animal.paused_reason == "billing":
            animal.paused = False
            animal.paused_reason = None
            notifier.send(animal.id, current_user.fcm_token, "OBNOVENO",
                          f"Platba prošla, {display_name} je zase v provozu.")
    else:
        animal.paused = True
        animal.paused_reason = "billing"
        notifier.send(animal.id, current_user.fcm_token, "PLATBA SE NEZDAŘILA",
                      f"Nepodařilo se dobít peněženku - {display_name} je pozastavená, dokud to nespravíš.")

    db.commit()
    db.refresh(topup)

    if not result.success:
        raise HTTPException(402, f"payment failed: {result.message}")
    return topup


@router.get("/topups", response_model=list[schemas.TopUpOut])
def list_animal_topups(
    animal_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    animal = _get_owned_animal(animal_id, current_user, db)
    return (
        db.query(models.AnimalWalletTopUp)
        .filter(models.AnimalWalletTopUp.animal_id == animal.id)
        .order_by(models.AnimalWalletTopUp.created_at.desc())
        .all()
    )
