"""Admin-only endpoints - real farm management and a basic operational
overview. Every route here requires require_admin (see auth.py): either the
KVOC_ADMIN_TOKEN shared header, or a logged-in user with is_admin=True.
Nothing here is reachable without one of those - see docs/ADMIN.md.
"""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config, models, schemas
from ..auth import require_admin
from ..database import get_db
from ..integrations.notifications import get_notification_provider
from ..tick import run_animal_tick_for_all, run_tick_for_all

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/run-tick")
def run_tick(days_offset: int = 0, db: Session = Depends(get_db)):
    """Manually run the daily tick, optionally pretending it's `days_offset`
    days in the future - the backend equivalent of the frontend demo's
    "Posunout o den" button, for seeing a full week without waiting.
    Runs for hens *and* the other-livestock Animal table (see
    docs/LIVESTOCK.md) - one daily tick, same as scheduler.py's real job.
    """
    fake_today = dt.date.today() + dt.timedelta(days=days_offset)
    hen_count = run_tick_for_all(db, fake_today)
    animal_count = run_animal_tick_for_all(db, fake_today)
    return {"ran_for_hens": hen_count, "ran_for_animals": animal_count, "as_of_date": fake_today.isoformat()}


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

    # Added together with the rest of docs/LIVESTOCK.md's feature, but this
    # endpoint predates it and nobody came back to extend the overview -
    # an ops dashboard that quietly stopped covering a third of the
    # product the day that feature shipped isn't "done", see the "maximally
    # improve the backend" pass this was written in.
    total_animals = db.query(func.count(models.Animal.id)).scalar()
    active_animals = db.query(func.count(models.Animal.id)).filter(models.Animal.paused.is_(False)).scalar()
    total_meat_shares = db.query(func.count(models.MeatShare.id)).scalar()
    open_meat_shares = db.query(func.count(models.MeatShare.id)).filter(models.MeatShare.status == "open").scalar()
    meat_share_revenue_total = db.query(func.coalesce(func.sum(models.ShareContribution.amount_czk), 0)).scalar()

    return {
        "total_users": total_users,
        "total_hens": total_hens,
        "active_hens": active_hens,
        "paused_hens": total_hens - active_hens,
        "revenue_total_czk": revenue_total,
        "failed_topups": failed_topups,
        "total_animals": total_animals,
        "active_animals": active_animals,
        "paused_animals": total_animals - active_animals,
        "total_meat_shares": total_meat_shares,
        "open_meat_shares": open_meat_shares,
        "meat_share_revenue_total_czk": meat_share_revenue_total,
    }


@router.get("/users")
def list_users(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    """Paginated - an unbounded `SELECT *` of every account ever registered
    was fine to answer instantly when this project had a handful of test
    users (see this whole session's history), but "return literally
    everyone, no limit" is exactly the kind of thing that's cheap to write
    and expensive to have shipped once an admin dashboard is actually used
    against a real user base.
    """
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    total = db.query(func.count(models.User.id)).scalar()
    users = (
        db.query(models.User)
        .order_by(models.User.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    # One query for every user's hen count instead of one *per user*
    # (accessing u.hens in the loop below used to lazy-load it individually
    # each time - fine for a handful of test accounts, real N+1 the moment
    # there's a real number of users).
    hen_counts = dict(
        db.query(models.Hen.user_id, func.count(models.Hen.id))
        .filter(models.Hen.user_id.in_([u.id for u in users]))
        .group_by(models.Hen.user_id)
        .all()
    ) if users else {}
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "created_at": u.created_at,
                "hen_count": hen_counts.get(u.id, 0),
                "has_saved_payment_method": bool(u.stripe_customer_id),
                "is_admin": u.is_admin,
            }
            for u in users
        ],
    }


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


# ---------------------------- other livestock (docs/LIVESTOCK.md) ----------------------------

@router.post("/farms/{key}/animal-offerings", status_code=201)
def add_animal_offering(key: str, payload: schemas.AnimalOfferingCreate, db: Session = Depends(get_db)):
    """Lets a farm actually offer a species/product combo - see
    models.FarmAnimalOffering. Without this, POST /animals refuses every
    adoption for that farm with 404, on purpose (a farm doesn't make
    goat milk just because the *species* exists in config.ANIMAL_PRODUCTS).

    A typed request body (schemas.AnimalOfferingCreate), not three loose
    query parameters - every other write endpoint in this API takes a real
    body; this one was the one exception, which meant no schema validation
    (an empty species string reached this far before), no OpenAPI-documented
    request shape, and awkward-to-construct calls from any real client.
    """
    farm = db.query(models.Farm).filter(models.Farm.key == key).first()
    if farm is None:
        raise HTTPException(404, f"unknown farm key '{key}'")
    valid = config.ANIMAL_PRODUCTS.get(payload.species)
    if valid is None or payload.product not in valid:
        raise HTTPException(400, f"'{payload.species}' doesn't make '{payload.product}' - see GET /animals/available-products")
    existing = (
        db.query(models.FarmAnimalOffering)
        .filter(
            models.FarmAnimalOffering.farm_id == farm.id,
            models.FarmAnimalOffering.species == payload.species,
            models.FarmAnimalOffering.product == payload.product,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(409, f"'{farm.name}' already offers {payload.species}/{payload.product}")
    offering = models.FarmAnimalOffering(
        farm_id=farm.id, species=payload.species, product=payload.product, weekly_capacity=payload.weekly_capacity,
    )
    db.add(offering)
    db.commit()
    return {"farm_key": key, "species": payload.species, "product": payload.product, "weekly_capacity": payload.weekly_capacity}


@router.post("/meat-shares", response_model=schemas.MeatShareOut, status_code=201)
def create_meat_share(payload: schemas.MeatShareCreate, db: Session = Depends(get_db)):
    """Listing a real animal for a share sale - see docs/LIVESTOCK.md for
    what still has to be true in the real world before this represents an
    actual animal (same caveat as create_farm above for a farm itself)."""
    if payload.species not in config.MEAT_SHARE_SPECIES:
        raise HTTPException(400, f"'{payload.species}' isn't a meat-share species - see config.MEAT_SHARE_SPECIES")
    farm = db.query(models.Farm).filter(models.Farm.key == payload.farm_key).first()
    if farm is None:
        raise HTTPException(404, f"unknown farm_key '{payload.farm_key}'")
    share = models.MeatShare(
        farm_id=farm.id, species=payload.species, label=payload.label,
        total_shares=payload.total_shares, price_per_share_czk=payload.price_per_share_czk,
        includes_hide=payload.includes_hide, expected_ready_date=payload.expected_ready_date,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    out = schemas.MeatShareOut.model_validate(share)
    out.shares_taken = 0
    return out


@router.post("/meat-shares/{share_id}/mark-ready", response_model=schemas.MeatShareOut)
def mark_meat_share_ready(share_id: int, payload: schemas.MarkShareReadyIn, db: Session = Depends(get_db)):
    """Records the real slaughter yield (a real-world event this software
    never triggers or witnesses - see models.MeatShare) and notifies every
    contributor of their computed portion. Doesn't ship anything - see
    docs/LIVESTOCK.md for why fulfillment itself stays outside this app."""
    share = db.get(models.MeatShare, share_id)
    if share is None:
        raise HTTPException(404, "meat share not found")
    if share.status not in ("open", "full"):
        raise HTTPException(409, f"share is already '{share.status}'")

    share.total_yield_kg = payload.total_yield_kg
    share.status = "ready"
    db.commit()
    db.refresh(share)

    notifier = get_notification_provider()
    for contribution in share.contributions:
        payout = round(payload.total_yield_kg * contribution.shares / share.total_shares, 2)
        owner = db.get(models.User, contribution.user_id)
        notifier.send(
            share.id, owner.fcm_token if owner else None, "MASO PŘIPRAVENO",
            f"'{share.label}' je hotová - tvůj podíl je {payout} kg" + (" + kůže" if share.includes_hide else "") + ".",
        )

    out = schemas.MeatShareOut.model_validate(share)
    out.shares_taken = sum(c.shares for c in share.contributions)
    return out
