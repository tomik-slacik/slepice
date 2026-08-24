"""FastAPI application entry point.

Run with:      python run.py
or directly:   uvicorn app.main:app --reload

Interactive API docs once it's running: http://127.0.0.1:8000/docs
"""
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Windows terminals often default to a legacy codepage that mangles the
# Czech diacritics in the demo notification text (e.g. "K�" instead of
# "Kč"). The data itself is fine either way (confirmed over real HTTP) -
# this just makes the console log readable too.
for _stream in (sys.stdout, sys.stderr):
    if getattr(_stream, "encoding", "").lower() != "utf-8":
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

from . import models  # noqa: F401  (registers models on Base before init_db)
from .database import SessionLocal, init_db
from .routers import admin, farms, hens
from .scheduler import start_scheduler, stop_scheduler
from .seed import seed_farms


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_farms(db)
    finally:
        db.close()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Kvoč API",
    description="Technický základ appky Kvoč — adopce slepičky, denní krmení, peněženka a páteční svoz.",
    version="0.1.0",
    lifespan=lifespan,
)

# TODO: lock this down to the real frontend's origin before deploying anywhere public.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(farms.router)
app.include_router(hens.router)
app.include_router(admin.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
