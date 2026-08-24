"""FastAPI application entry point.

Run with:      python run.py
or directly:   uvicorn app.main:app --reload

Interactive API docs once it's running: http://127.0.0.1:8000/docs
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

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

from . import config, models  # noqa: F401  (models import registers them on Base before init_db)
from .database import SessionLocal, init_db
from .logging_setup import setup_logging
from .routers import admin, auth, farms, hens, wallet
from .scheduler import start_scheduler, stop_scheduler
from .seed import seed_farms

logger = setup_logging()


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

# See config.CORS_ORIGINS - the bundled webapp is same-origin and never
# needs this; it's for any separately-hosted client. Set KVOC_CORS_ORIGINS
# before deploying anywhere the wallet/payment endpoints matter.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.mount("/app", StaticFiles(directory=Path(__file__).parent / "webapp", html=True), name="webapp")

app.include_router(auth.router)
app.include_router(farms.router)
app.include_router(hens.router)
app.include_router(wallet.router)
app.include_router(admin.router)


@app.exception_handler(Exception)
async def log_unhandled_exceptions(request: Request, exc: Exception):
    """Every unhandled exception gets a full traceback in the log (see
    logging_setup.py) instead of just vanishing into a bare 500 nobody
    finds out about until a user complains. The client still only ever
    sees a generic message - never exc's actual text, which could leak
    internals (a query, a file path, a stack frame).
    """
    logger.exception("unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
