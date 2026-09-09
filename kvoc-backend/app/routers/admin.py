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
from ..geo import haversine_km
from ..integrations.notifications import get_notification_provider
from ..tick import run_animal_tick_for_all, run_tick_for_all

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_SPECIES_LABEL_CS = {"goat": "Koza", "sheep": "Ovce", "cow": "Kráva"}


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

    # animal_wallet.py (docs/LIVESTOCK.md's other honestly-documented gap,
    # closed in the same pass) - own line item, not folded into
    # revenue_total_czk above, same reasoning as meat_share_revenue_total_czk
    # having its own line instead of silently changing what an existing
    # field already means to callers
    animal_wallet_revenue_total = (
        db.query(func.coalesce(func.sum(models.AnimalWalletTopUp.amount_czk), 0))
        .filter(models.AnimalWalletTopUp.status == "succeeded")
        .scalar()
    )
    failed_animal_topups = (
        db.query(func.count(models.AnimalWalletTopUp.id))
        .filter(models.AnimalWalletTopUp.status == "failed")
        .scalar()
    )

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
        "animal_wallet_revenue_total_czk": animal_wallet_revenue_total,
        "failed_animal_topups": failed_animal_topups,
        "total_meat_shares": total_meat_shares,
        "open_meat_shares": open_meat_shares,
        "meat_share_revenue_total_czk": meat_share_revenue_total,
    }


@router.get("/stats/timeseries")
def get_stats_timeseries(days: int = 14, db: Session = Depends(get_db)):
    """Daily new-signup and revenue counts for the last `days` days
    (default 14) - /stats above only ever gave a current snapshot, never a
    trend (see the former "žádný graf v čase" line in docs/ADMIN.md).
    Revenue here means real money actually charged (wallet top-ups, meat-
    share contributions), same definition /stats already uses - not a
    projection.

    Bucketed here in Python rather than a DB-side date-trunc, so it behaves
    identically on SQLite (dev) and Postgres (production, see
    docs/DEPLOYMENT.md) instead of depending on either dialect's date
    functions - the data volumes this app deals with make that cheap.
    """
    days = max(1, min(days, 90))
    since_date = dt.date.today() - dt.timedelta(days=days - 1)
    since = dt.datetime.combine(since_date, dt.time.min, tzinfo=dt.timezone.utc)

    buckets = {}
    for i in range(days):
        d = since_date + dt.timedelta(days=i)
        buckets[d.isoformat()] = {"date": d.isoformat(), "new_users": 0, "revenue_czk": 0}

    def _bucket_for(created_at: dt.datetime):
        # SQLite round-trips datetimes as naive (drops the tzinfo the model
        # default attaches on write) - .date() is correct either way, only
        # a naive/aware *comparison* would need care, and there isn't one here
        return buckets.get(created_at.date().isoformat())

    for (created_at,) in db.query(models.User.created_at).filter(models.User.created_at >= since).all():
        b = _bucket_for(created_at)
        if b:
            b["new_users"] += 1

    topups = (
        db.query(models.WalletTopUp.created_at, models.WalletTopUp.amount_czk)
        .filter(models.WalletTopUp.status == "succeeded", models.WalletTopUp.created_at >= since)
        .all()
    )
    animal_topups = (
        db.query(models.AnimalWalletTopUp.created_at, models.AnimalWalletTopUp.amount_czk)
        .filter(models.AnimalWalletTopUp.status == "succeeded", models.AnimalWalletTopUp.created_at >= since)
        .all()
    )
    contributions = (
        db.query(models.ShareContribution.created_at, models.ShareContribution.amount_czk)
        .filter(models.ShareContribution.created_at >= since)
        .all()
    )
    for created_at, amount in [*topups, *animal_topups, *contributions]:
        b = _bucket_for(created_at)
        if b:
            b["revenue_czk"] += amount

    return {"days": days, "series": [buckets[k] for k in sorted(buckets)]}


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


@router.get("/users/{user_id}")
def get_user_detail(user_id: int, db: Session = Depends(get_db)):
    """The one-line-per-user list above deliberately doesn't carry hen/animal
    ids (a list of hundreds of users doesn't want every hen's id inline) -
    this is where a support conversation ("can you pause my hen, I'm on
    holiday") actually gets acted on, via PATCH /admin/hens/{id} below.
    """
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    return {
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at,
        "is_admin": user.is_admin,
        "has_saved_payment_method": bool(user.stripe_customer_id),
        "hens": [
            {
                "id": h.id, "hen_name": h.hen_name, "farm_id": h.farm_id,
                "daily_amount": h.daily_amount, "address": h.address, "paused": h.paused,
            }
            for h in user.hens
        ],
        "animals": [
            {
                "id": a.id, "species": a.species, "product": a.product, "name": a.name,
                "farm_id": a.farm_id, "daily_amount": a.daily_amount, "address": a.address, "paused": a.paused,
            }
            for a in user.animals
        ],
    }


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Hard delete, cascading to everything under the account - hens,
    animals, meat-share contributions and everything under those in turn
    (see the cascade="all, delete-orphan" relationships on User in
    models.py) - the same mechanism DELETE /auth/me already relies on for a
    user deleting their own account, just admin-triggered for someone else's.
    A real need, not just moderation - see docs/BUSINESS_CHECKLIST.md's
    GDPR "žádosti o výmaz" line, which this was the missing piece for.

    Refuses to delete an admin account through this endpoint. Not because
    it's technically any different to cascade-delete - because a careless
    click removing the only admin account (or the one you're using right
    now) is a much worse failure mode than the same click on an ordinary
    customer, and there's no "undo" on a hard delete.
    """
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    if user.is_admin:
        raise HTTPException(400, "won't delete an admin account through this endpoint")
    db.delete(user)
    db.commit()


@router.patch("/hens/{hen_id}", response_model=schemas.HenOut)
def admin_update_hen(hen_id: int, payload: schemas.HenUpdate, db: Session = Depends(get_db)):
    """Same fields a customer can change themselves (PATCH /hens/{id}), just
    without the ownership check - so a support request can actually be
    acted on instead of only relayed back to the user ("please pause it
    yourself"). See docs/ADMIN.md.
    """
    hen = db.get(models.Hen, hen_id)
    if hen is None:
        raise HTTPException(404, "hen not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(hen, field, value)
    db.commit()
    db.refresh(hen)
    return hen


@router.patch("/animals/{animal_id}", response_model=schemas.AnimalOut)
def admin_update_animal(animal_id: int, payload: schemas.AnimalUpdate, db: Session = Depends(get_db)):
    """Same as admin_update_hen above, for the other-livestock side."""
    animal = db.get(models.Animal, animal_id)
    if animal is None:
        raise HTTPException(404, "animal not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(animal, field, value)
    db.commit()
    db.refresh(animal)
    return animal


@router.get("/farms/{key}/delivery-route")
def get_delivery_route(key: str, db: Session = Depends(get_db)):
    """Turns "every active hen/animal at this farm" into one ordered
    delivery route instead of a random stop order - see docs/LOGISTICS.md's
    "co appka může pomoct" section, which this is the previously-missing
    piece for. Greedy nearest-neighbor from the farm's own location: not a
    real-roads routing engine (nothing like that is wired up here, and
    straight-line "as the crow flies" distance is all Hen.lat/lng and
    Farm.lat/lng give us) - but a long way better than the stop order
    happening to match whoever adopted in what order.

    Only covers hens/animals that (a) aren't paused this week and (b) have
    a saved lat/lng - see models.Hen.lat's comment for why that can be
    null. Anyone missing either is listed separately under `unlocated`
    rather than silently dropped, so nobody's delivery goes unplanned just
    because the app doesn't know where to draw them on the route.
    """
    farm = db.query(models.Farm).filter(models.Farm.key == key).first()
    if farm is None:
        raise HTTPException(404, f"unknown farm key '{key}'")

    located, unlocated = [], []
    for hen in db.query(models.Hen).filter(models.Hen.farm_id == farm.id, models.Hen.paused.is_(False)).all():
        entry = {"kind": "hen", "id": hen.id, "name": hen.hen_name, "address": hen.address, "lat": hen.lat, "lng": hen.lng}
        (located if hen.lat is not None and hen.lng is not None else unlocated).append(entry)
    for animal in db.query(models.Animal).filter(models.Animal.farm_id == farm.id, models.Animal.paused.is_(False)).all():
        label = animal.name or _SPECIES_LABEL_CS.get(animal.species, animal.species)
        entry = {"kind": "animal", "id": animal.id, "name": label, "address": animal.address, "lat": animal.lat, "lng": animal.lng}
        (located if animal.lat is not None and animal.lng is not None else unlocated).append(entry)

    if farm.lat is None or farm.lng is None:
        # nothing to anchor a route to at all - every stop just goes to
        # "unlocated" rather than pretending an order that isn't real
        return {
            "farm_key": key, "farm_name": farm.name, "route": [], "total_km": None,
            "unlocated": located + unlocated,
            "note": "farma sama nemá uloženou polohu, trasu nejde spočítat",
        }

    ordered = []
    remaining = located[:]
    cur_lat, cur_lng = farm.lat, farm.lng
    running_km = 0.0
    while remaining:
        remaining.sort(key=lambda s: haversine_km(cur_lat, cur_lng, s["lat"], s["lng"]))
        nxt = remaining.pop(0)
        leg_km = haversine_km(cur_lat, cur_lng, nxt["lat"], nxt["lng"])
        running_km += leg_km
        ordered.append({**nxt, "leg_km": leg_km, "running_km": round(running_km, 1)})
        cur_lat, cur_lng = nxt["lat"], nxt["lng"]

    return {
        "farm_key": key, "farm_name": farm.name, "route": ordered,
        "total_km": round(running_km, 1), "unlocated": unlocated,
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
