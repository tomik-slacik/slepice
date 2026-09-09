"""Meat shares - see models.MeatShare's docstring for the lifecycle, and
docs/LIVESTOCK.md for the real-world reasoning (one cow/goat/sheep is too
much meat for one household, so several customers pool contributions
instead of one customer "owning" the whole animal).

Admin-only actions (creating a share, marking one ready with the real
yield) live in routers/admin.py, not here - this file is the customer-
facing browse/contribute surface.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..integrations.notifications import get_notification_provider
from ..integrations.payments import get_payment_provider

router = APIRouter(prefix="/meat-shares", tags=["meat-shares"])


def shares_taken(share: models.MeatShare) -> int:
    return sum(c.shares for c in share.contributions)


def to_out(share: models.MeatShare, current_user: models.User) -> schemas.MeatShareOut:
    out = schemas.MeatShareOut.model_validate(share)
    out.shares_taken = shares_taken(share)
    mine = [c for c in share.contributions if c.user_id == current_user.id]
    out.my_shares = sum(c.shares for c in mine)
    if out.my_shares and share.total_yield_kg is not None:
        out.my_payout_kg = round(share.total_yield_kg * out.my_shares / share.total_shares, 2)
    return out


@router.get("", response_model=List[schemas.MeatShareOut])
def list_meat_shares(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    shares = db.query(models.MeatShare).order_by(models.MeatShare.created_at.desc()).all()
    return [to_out(s, current_user) for s in shares]


@router.get("/{share_id}", response_model=schemas.MeatShareOut)
def get_meat_share(share_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    share = db.get(models.MeatShare, share_id)
    if share is None:
        raise HTTPException(404, "meat share not found")
    return to_out(share, current_user)


@router.post("/{share_id}/contribute", response_model=schemas.MeatShareOut)
def contribute_to_share(
    share_id: int,
    payload: schemas.ShareContributeIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    share = db.get(models.MeatShare, share_id)
    if share is None:
        raise HTTPException(404, "meat share not found")
    if share.status != "open":
        raise HTTPException(409, f"this share is '{share.status}', not open for contributions")

    taken = shares_taken(share)
    if taken + payload.shares > share.total_shares:
        raise HTTPException(409, f"only {share.total_shares - taken} share(s) left on '{share.label}'")

    if not current_user.stripe_customer_id:
        raise HTTPException(400, "no saved payment method - call POST /hens/{any_hen_id}/wallet/setup-intent first")

    amount_czk = payload.shares * share.price_per_share_czk
    provider = get_payment_provider()
    result = provider.charge_saved_method(current_user.stripe_customer_id, amount_czk)
    if not result.success:
        raise HTTPException(402, f"payment failed: {result.message}")

    db.add(models.ShareContribution(
        meat_share_id=share.id, user_id=current_user.id, shares=payload.shares,
        amount_czk=amount_czk, provider_reference=result.provider_reference,
    ))
    if taken + payload.shares >= share.total_shares:
        share.status = "full"
    db.commit()
    db.refresh(share)

    get_notification_provider().send(
        share.id, current_user.fcm_token, "PODÍL",
        f"Koupil sis {payload.shares} podíl(y) na '{share.label}' za {amount_czk} Kč.",
    )
    return to_out(share, current_user)


@router.delete("/{share_id}/contribution", response_model=schemas.MeatShareOut)
def cancel_my_contribution(
    share_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Undo everything *this* user has contributed to one share and refund
    it - all-or-nothing, the same granularity as cancelling a hen or animal
    (DELETE /hens/{id}, DELETE /animals/{id}), not a "give back just one of
    my shares" partial refund.

    Only while the share hasn't moved past taking contributions: once it's
    `processing` or later the farm already committed the real animal for
    slaughter on the strength of what was pledged, so a refund past that
    point isn't offered. Returns the updated share (unlike the hen/animal
    DELETEs, which return 204) because the share itself still exists -
    only this user's stake in it is gone.
    """
    share = db.get(models.MeatShare, share_id)
    if share is None:
        raise HTTPException(404, "meat share not found")
    if share.status not in ("open", "full"):
        raise HTTPException(409, f"'{share.label}' is already {share.status} - too late to cancel a contribution")

    mine = [c for c in share.contributions if c.user_id == current_user.id]
    if not mine:
        raise HTTPException(404, "you have no contribution on this share")

    provider = get_payment_provider()
    refunded_czk = 0
    # refund+delete one at a time (not all-refund-then-all-delete) so a
    # failure partway through never leaves a contribution refunded in
    # Stripe but still showing as active here
    for contribution in mine:
        result = provider.refund_charge(contribution.provider_reference, contribution.amount_czk)
        if not result.success:
            db.commit()
            raise HTTPException(402, f"refund failed: {result.message}")
        refunded_czk += contribution.amount_czk
        db.delete(contribution)

    if share.status == "full":
        share.status = "open"
    db.commit()
    db.refresh(share)

    get_notification_provider().send(
        share.id, current_user.fcm_token, "VRÁCENO",
        f"Podíl na '{share.label}' zrušen, {refunded_czk} Kč vráceno.",
    )
    return to_out(share, current_user)
