"""Seeds the three demo farms the frontend already knows about, so a fresh
database isn't empty. Real farm onboarding would eventually need its own
admin / back-office flow - out of scope for this foundation.
"""
from sqlalchemy.orm import Session

from .models import Farm

_FARMS = [
    dict(key="lipa", name="Farma U Lípy", description="volný výběh · Sázava, 18 km"),
    dict(key="dvur", name="Dvůr Na Kopci", description="bio chov · Benešov, 24 km"),
    dict(key="polana", name="Polana Farm", description="volný výběh · Neveklov, 9 km"),
]


def seed_farms(db: Session) -> None:
    if db.query(Farm).count() > 0:
        return
    for f in _FARMS:
        db.add(Farm(**f))
    db.commit()
