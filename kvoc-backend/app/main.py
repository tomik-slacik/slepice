"""FastAPI application entry point.

Run with:      python run.py
or directly:   uvicorn app.main:app --reload

Interactive API docs once it's running: http://127.0.0.1:8000/docs
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

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
from .database import SessionLocal, get_db, init_db
from .logging_setup import setup_logging
from .middleware import RateLimitMiddleware, RequestLoggingMiddleware
from .routers import admin, animals, auth, farms, hens, meat_shares, wallet
from .scheduler import start_scheduler, stop_scheduler
from .seed import seed_animal_offerings, seed_farms, seed_meat_shares

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_farms(db)
        seed_animal_offerings(db)
        seed_meat_shares(db)
    finally:
        db.close()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Mazlík API",
    description="Technický základ appky Mazlík — adopce slepičky/kozy/ovce/krávy, denní krmení, peněženka a páteční svoz.",
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
# Middleware added below CORS, so it ends up *outside* it (Starlette builds
# the stack in reverse add order - the last one added runs first on the way
# in). Order that actually matters: a rate-limited request should never
# even reach CORS/routing, and every request - limited or not - should get
# logged with the same request id. See middleware.py for what each one does
# and doesn't do.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.mount("/app", StaticFiles(directory=Path(__file__).parent / "webapp", html=True), name="webapp")

app.include_router(auth.router)
app.include_router(farms.router)
app.include_router(hens.router)
app.include_router(wallet.router)
app.include_router(animals.router)
app.include_router(meat_shares.router)
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
def health(db: Session = Depends(get_db)):
    """A health check that only ever says "ok" isn't really checking
    anything - the process being up to answer HTTP at all was never in
    doubt. This actually exercises the one dependency that can fail
    independently of the process itself: the database. A load balancer or
    orchestrator using this to decide whether to send traffic here (or
    restart the container) gets a real answer, not a rubber stamp.
    """
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("health check: database unreachable")
        db_ok = False
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unreachable"},
    )
