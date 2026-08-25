"""Wires the daily business-logic tick (app/tick.py) to a real cron-like
schedule using APScheduler, so it actually fires once a day without anyone
having to remember to call it.

Started from app/main.py's lifespan handler. For local testing you don't
need to wait for the real clock - see POST /admin/run-tick instead.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from . import config
from .database import SessionLocal
from .tick import run_animal_tick_for_all, run_tick_for_all

_scheduler: Optional[BackgroundScheduler] = None


def _job() -> None:
    db = SessionLocal()
    try:
        today = dt.date.today()
        hen_count = run_tick_for_all(db, today)
        animal_count = run_animal_tick_for_all(db, today)
        print(f"[scheduler] daily tick ran for {hen_count} hen(s), {animal_count} other animal(s) at {dt.datetime.now().isoformat()}")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone=config.SCHEDULER_TIMEZONE)
    _scheduler.add_job(
        _job, "cron", hour=config.DAILY_TICK_HOUR, minute=config.DAILY_TICK_MINUTE, id="daily_tick"
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
