"""Development-only helpers.

Do not expose this router in any deployment reachable from the internet
without adding real authentication first - see the TODO below.
"""
import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..tick import run_tick_for_all

router = APIRouter(prefix="/admin", tags=["admin (dev only)"])


@router.post("/run-tick")
def run_tick(days_offset: int = 0, db: Session = Depends(get_db)):
    """Manually run the daily tick, optionally pretending it's `days_offset`
    days in the future. This is the backend equivalent of the frontend
    demo's "Posunout o den" button - lets you see a full week without
    waiting for real days to pass.

    TODO: this endpoint has no authentication and lets anyone advance every
    hen's clock at once. That's fine for local development; remove it or
    lock it down behind an admin-only auth check before deploying anywhere
    reachable from the internet.
    """
    fake_today = dt.date.today() + dt.timedelta(days=days_offset)
    count = run_tick_for_all(db, fake_today)
    return {"ran_for_hens": count, "as_of_date": fake_today.isoformat()}
