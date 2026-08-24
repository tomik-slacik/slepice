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
from .models import Delivery, FeedLogEntry, Hen, PausedDay

FEED_MESSAGES = [
    "dostala ranní zrníčko.",
    "se napila studánkové vody.",
    "se vyhřívala na sluníčku a hrabala se v hlíně.",
    "si pochutnala na tučném červíkovi.",
    "si protáhla křídla na dvorku.",
    "si hověla v čerstvé podestýlce.",
    "se proháněla po dvorku za motýlem.",
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
