"""Seeds the demo farms the frontend already knows about, so a fresh
database isn't empty. Real farm onboarding would eventually need its own
admin / back-office flow - out of scope for this foundation.

Coordinates are real town-center points (demo-grade precision, not a
survey) for actual places in Central Bohemia - the farms themselves are
still made up for this demo (no real farmer has actually signed up), but
the "find farms near me" distance math against these coordinates is real.
Same roster as frontend/index.html's FARMS array - keep them in sync.
"""
from sqlalchemy.orm import Session

from .models import Farm

_FARMS = [
    dict(key="lipa", name="Farma U Lípy", description="volný výběh", lat=49.8564, lng=14.8636, weekly_capacity=60),
    dict(key="dvur", name="Dvůr Na Kopci", description="bio chov", lat=49.7847, lng=14.6873, weekly_capacity=40),
    dict(key="polana", name="Polana Farm", description="volný výběh", lat=49.7994, lng=14.5589, weekly_capacity=80),
    dict(key="ricany", name="Zahrada Pod Lesem", description="bio chov", lat=49.9917, lng=14.6650, weekly_capacity=30),
    dict(key="beroun", name="Farma Beránek", description="volný výběh", lat=49.9639, lng=14.0725, weekly_capacity=50),
    dict(key="kladno", name="Dvůr U Rybníka", description="bio chov", lat=50.1477, lng=14.1030, weekly_capacity=35),
    dict(key="melnik", name="Vinný Dvůr", description="volný výběh", lat=50.3520, lng=14.4739, weekly_capacity=45),
    dict(key="kutnahora", name="Stříbrná Farma", description="bio chov", lat=49.9481, lng=15.2683, weekly_capacity=25),
]


def seed_farms(db: Session) -> None:
    """Idempotent per farm key, not just "run once on an empty table" - so
    adding a new farm to _FARMS above (like this update did, 3 -> 8) reaches
    an existing dev database too, on the next boot, without wiping it.
    """
    existing = {f.key: f for f in db.query(Farm).all()}
    changed = False
    for row in _FARMS:
        current = existing.get(row["key"])
        if current is None:
            db.add(Farm(**row))
            changed = True
        else:
            if current.lat is None or current.lng is None:
                # backfill coordinates onto a farm that predates this field
                current.lat = row["lat"]
                current.lng = row["lng"]
                changed = True
            if current.weekly_capacity is None:
                current.weekly_capacity = row["weekly_capacity"]
                changed = True
    if changed:
        db.commit()
