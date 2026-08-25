"""The daily business-logic tick - the real-world equivalent of the demo
frontend's "advance day" button.

In production this runs once a day per hen via the real cron schedule in
scheduler.py. For local testing / demos you don't have to wait for the
clock - see POST /admin/run-tick.
"""
from __future__ import annotations

import datetime as dt
import random
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import config
from .integrations.notifications import get_notification_provider
from .models import Animal, AnimalDelivery, AnimalPausedDay, AnimalProductLogEntry, Delivery, FeedLogEntry, Hen, PausedDay

FEED_MESSAGES = [
    "dostala ranní zrníčko.",
    "se napila studánkové vody.",
    "se vyhřívala na sluníčku a hrabala se v hlíně.",
    "si pochutnala na tučném červíkovi.",
    "si protáhla křídla na dvorku.",
    "si hověla v čerstvé podestýlce.",
    "se proháněla po dvorku za motýlem.",
]

# Shared across goat/sheep/cow - generic enough to fit any of them, unlike
# FEED_MESSAGES above which is written hen-specific on purpose (pecking,
# wings). See docs/LIVESTOCK.md on why this is one shared pool instead of
# bespoke text per species for a first pass.
ANIMAL_CARE_MESSAGES = [
    "se pásla na louce.",
    "dostala čerstvé seno.",
    "se napila z napajedla.",
    "si hověla ve stínu.",
    "dostala kartáčování.",
    "si protáhla nohy na dvoře.",
]


def _monday_of(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def run_tick_for_hen(db: Session, hen: Hen, today: dt.date) -> None:
    """Advance one hen's state by a single day. Idempotent: calling this
    again for a day already processed is a safe no-op for that day.
    """
    notifier = get_notification_provider()
    device_token = hen.owner.fcm_token if hen.owner else None

    if today.weekday() < 5:  # Monday..Friday
        if hen.paused:
            already = (
                db.query(PausedDay)
                .filter(PausedDay.hen_id == hen.id, PausedDay.date == today)
                .first()
            )
            if already is None:
                db.add(PausedDay(hen_id=hen.id, date=today))
        else:
            existing = (
                db.query(FeedLogEntry)
                .filter(
                    FeedLogEntry.hen_id == hen.id,
                    FeedLogEntry.date == today,
                    FeedLogEntry.is_bonus.is_(False),
                )
                .first()
            )
            if existing is None:
                msg = f"{hen.hen_name} {random.choice(FEED_MESSAGES)}"
                db.add(FeedLogEntry(hen_id=hen.id, date=today, amount=hen.daily_amount, message=msg, is_bonus=False))
                notifier.send(hen.id, device_token, f"-{hen.daily_amount} Kč", msg)

                if random.random() < config.BONUS_CHANCE:
                    bonus_msg = (
                        f"{hen.hen_name} má dobrý den — snesla vejce navíc. "
                        "Přidáme ho do páteční bedýnky."
                    )
                    db.add(FeedLogEntry(hen_id=hen.id, date=today, amount=0, message=bonus_msg, is_bonus=True))
                    notifier.send(hen.id, device_token, "BONUS", bonus_msg)

                if today.weekday() == config.DELIVERY_WEEKDAY:
                    monday = _monday_of(today)
                    rows = (
                        db.query(FeedLogEntry.amount)
                        .filter(
                            FeedLogEntry.hen_id == hen.id,
                            FeedLogEntry.date >= monday,
                            FeedLogEntry.date <= today,
                            FeedLogEntry.is_bonus.is_(False),
                        )
                        .all()
                    )
                    total = sum(a for (a,) in rows)
                    eggs = max(1, round(total / config.KC_PER_EGG))
                    db.add(Delivery(
                        hen_id=hen.id, week_start=monday, date=today,
                        amount=total, eggs=eggs, status="transit",
                    ))
                    notifier.send(
                        hen.id, device_token, "PÁTEK",
                        f"Tenhle týden jsi {hen.hen_name} krmil. Dnes odpoledne dorazí {eggs} vajec.",
                    )

    last_delivery = (
        db.query(Delivery)
        .filter(Delivery.hen_id == hen.id, Delivery.status == "transit")
        .order_by(Delivery.date.desc())
        .first()
    )
    if last_delivery is not None and (today - last_delivery.date).days >= 1:
        last_delivery.status = "delivered"
        notifier.send(hen.id, device_token, "DORUČENO", f"{last_delivery.eggs} vajec právě dorazilo ke dveřím.")

    db.commit()


def effective_today_for_hen(db: Session, hen: Hen) -> dt.date:
    """The date to treat as "today" when computing this hen's wallet/streak
    for display.

    Normally just the real date - but POST /admin/run-tick (see
    app/routers/admin.py) can advance a hen's data into the future for
    demo/testing purposes without any server-wide "current date" changing.
    Without this, a demo-advanced hen's balance and streak would silently
    stay frozen at whatever the real day's numbers were, even though new
    feed-log entries keep appearing - exactly the mismatch a live click
    through the UI caught (week_balance/streak stuck after "Posunout o den"
    while /feed-log clearly showed a new entry). So: if the latest date we
    actually have data for is further ahead than the real date, that later
    date is "today" for this hen.
    """
    real_today = dt.date.today()
    latest = (
        db.query(func.max(FeedLogEntry.date))
        .filter(FeedLogEntry.hen_id == hen.id)
        .scalar()
    )
    if latest and latest > real_today:
        return latest
    return real_today


def run_tick_for_all(db: Session, today: Optional[dt.date] = None) -> int:
    today = today or dt.date.today()
    hens = db.query(Hen).all()
    for hen in hens:
        run_tick_for_hen(db, hen, today)
    return len(hens)


def compute_week_balance(db: Session, hen: Hen, today: Optional[dt.date] = None) -> int:
    today = today or dt.date.today()
    monday = _monday_of(today)
    rows = (
        db.query(FeedLogEntry.amount)
        .filter(
            FeedLogEntry.hen_id == hen.id,
            FeedLogEntry.date >= monday,
            FeedLogEntry.date <= today,
            FeedLogEntry.is_bonus.is_(False),
        )
        .all()
    )
    return sum(a for (a,) in rows)


def compute_streak(db: Session, hen: Hen, today: Optional[dt.date] = None) -> int:
    """Consecutive weekdays fed, most recent first. A paused day freezes the
    streak (neither adds to it nor breaks it) - a real gap breaks it.
    """
    today = today or dt.date.today()
    streak = 0
    d = today
    for _ in range(370):
        if d.weekday() < 5:
            fed = (
                db.query(FeedLogEntry)
                .filter(FeedLogEntry.hen_id == hen.id, FeedLogEntry.date == d, FeedLogEntry.is_bonus.is_(False))
                .first()
            )
            if fed is not None:
                streak += 1
            else:
                was_paused = (
                    db.query(PausedDay)
                    .filter(PausedDay.hen_id == hen.id, PausedDay.date == d)
                    .first()
                )
                if was_paused is not None:
                    pass  # frozen, not broken
                elif d == today:
                    pass  # today just hasn't ticked yet
                else:
                    break
        d = d - dt.timedelta(days=1)
    return streak


# ============================================================================
# Other livestock (see docs/LIVESTOCK.md) - same shape as the hen functions
# above, parameterized by species/product via config.ANIMAL_PRODUCTS instead
# of hardcoded eggs/Kč-per-egg math.
# ============================================================================


def run_tick_for_animal(db: Session, animal: Animal, today: dt.date) -> None:
    notifier = get_notification_provider()
    device_token = animal.owner.fcm_token if animal.owner else None
    product_info = config.ANIMAL_PRODUCTS.get(animal.species, {}).get(animal.product, {})
    kc_per_unit = product_info.get("kc_per_unit", 20)
    unit_label = product_info.get("unit_label", "jednotek")

    if today.weekday() < 5:
        if animal.paused:
            already = (
                db.query(AnimalPausedDay)
                .filter(AnimalPausedDay.animal_id == animal.id, AnimalPausedDay.date == today)
                .first()
            )
            if already is None:
                db.add(AnimalPausedDay(animal_id=animal.id, date=today))
        else:
            existing = (
                db.query(AnimalProductLogEntry)
                .filter(
                    AnimalProductLogEntry.animal_id == animal.id,
                    AnimalProductLogEntry.date == today,
                    AnimalProductLogEntry.is_bonus.is_(False),
                )
                .first()
            )
            if existing is None:
                msg = f"{animal.name or animal.species.capitalize()} {random.choice(ANIMAL_CARE_MESSAGES)}"
                db.add(AnimalProductLogEntry(animal_id=animal.id, date=today, amount=animal.daily_amount, message=msg, is_bonus=False))
                notifier.send(animal.id, device_token, f"-{animal.daily_amount} Kč", msg)

                if random.random() < config.BONUS_CHANCE:
                    bonus_msg = (
                        f"{animal.name or animal.species.capitalize()} má dobrý den — o trochu víc "
                        f"{unit_label} navíc do páteční dodávky."
                    )
                    db.add(AnimalProductLogEntry(animal_id=animal.id, date=today, amount=0, message=bonus_msg, is_bonus=True))
                    notifier.send(animal.id, device_token, "BONUS", bonus_msg)

                if today.weekday() == config.DELIVERY_WEEKDAY:
                    monday = _monday_of(today)
                    rows = (
                        db.query(AnimalProductLogEntry.amount)
                        .filter(
                            AnimalProductLogEntry.animal_id == animal.id,
                            AnimalProductLogEntry.date >= monday,
                            AnimalProductLogEntry.date <= today,
                            AnimalProductLogEntry.is_bonus.is_(False),
                        )
                        .all()
                    )
                    total = sum(a for (a,) in rows)
                    units = round(total / kc_per_unit, 1) if kc_per_unit else 0.0
                    db.add(AnimalDelivery(
                        animal_id=animal.id, week_start=monday, date=today,
                        amount=total, units=units, status="transit",
                    ))
                    notifier.send(
                        animal.id, device_token, "PÁTEK",
                        f"Tenhle týden jsi {animal.name or animal.species} krmil. Dnes odpoledne dorazí {units} {unit_label}.",
                    )

    last_delivery = (
        db.query(AnimalDelivery)
        .filter(AnimalDelivery.animal_id == animal.id, AnimalDelivery.status == "transit")
        .order_by(AnimalDelivery.date.desc())
        .first()
    )
    if last_delivery is not None and (today - last_delivery.date).days >= 1:
        last_delivery.status = "delivered"
        notifier.send(animal.id, device_token, "DORUČENO", f"{last_delivery.units} {unit_label} právě dorazilo ke dveřím.")

    db.commit()


def effective_today_for_animal(db: Session, animal: Animal) -> dt.date:
    """Same reasoning as effective_today_for_hen above."""
    real_today = dt.date.today()
    latest = (
        db.query(func.max(AnimalProductLogEntry.date))
        .filter(AnimalProductLogEntry.animal_id == animal.id)
        .scalar()
    )
    if latest and latest > real_today:
        return latest
    return real_today


def run_animal_tick_for_all(db: Session, today: Optional[dt.date] = None) -> int:
    today = today or dt.date.today()
    animals = db.query(Animal).all()
    for animal in animals:
        run_tick_for_animal(db, animal, today)
    return len(animals)


def compute_animal_week_balance(db: Session, animal: Animal, today: Optional[dt.date] = None) -> int:
    today = today or dt.date.today()
    monday = _monday_of(today)
    rows = (
        db.query(AnimalProductLogEntry.amount)
        .filter(
            AnimalProductLogEntry.animal_id == animal.id,
            AnimalProductLogEntry.date >= monday,
            AnimalProductLogEntry.date <= today,
            AnimalProductLogEntry.is_bonus.is_(False),
        )
        .all()
    )
    return sum(a for (a,) in rows)


def compute_animal_streak(db: Session, animal: Animal, today: Optional[dt.date] = None) -> int:
    today = today or dt.date.today()
    streak = 0
    d = today
    for _ in range(370):
        if d.weekday() < 5:
            fed = (
                db.query(AnimalProductLogEntry)
                .filter(AnimalProductLogEntry.animal_id == animal.id, AnimalProductLogEntry.date == d, AnimalProductLogEntry.is_bonus.is_(False))
                .first()
            )
            if fed is not None:
                streak += 1
            else:
                was_paused = (
                    db.query(AnimalPausedDay)
                    .filter(AnimalPausedDay.animal_id == animal.id, AnimalPausedDay.date == d)
                    .first()
                )
                if was_paused is not None:
                    pass
                elif d == today:
                    pass
                else:
                    break
        d = d - dt.timedelta(days=1)
    return streak
