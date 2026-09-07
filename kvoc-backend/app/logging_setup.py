"""Structured error logging - the safe, no-account-needed default.

Every unhandled exception gets logged (full traceback + which request
caused it) to stderr and to a local rotating file, instead of just crashing
that one request silently. This is NOT the same as a real error-tracking
service (Sentry, etc.) - nobody gets paged, there's no dashboard, no
alerting, no de-duplication across occurrences. Wiring one of those is a
real account/integration decision (see the bottom of this file for the
mechanical part of that swap) - this module is what runs until you do.

Every log line (not just exceptions - see RequestIdFilter/request_id_ctx
below) also carries the id of the request it happened during, so "what led
up to this error" or "what did this one confusing user report actually do"
is a grep for one id across the log file, instead of guessing from
timestamps alone. See main.py's RequestLoggingMiddleware for where that id
comes from and how a client can supply/receive it.
"""
from __future__ import annotations

import contextvars
import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"

# Set by main.py's RequestLoggingMiddleware for the duration of one request;
# "-" outside any request (startup/shutdown, the daily tick running on its
# own schedule rather than in response to an HTTP call). A contextvar
# rather than a request-scoped logger/adapter passed around everywhere so
# *any* module's plain `logging.getLogger("kvoc")` call picks it up
# automatically, without every function needing a `request` argument.
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("kvoc")
    if logger.handlers:
        return logger  # already configured (e.g. --reload re-imported this module)

    logger.setLevel(logging.INFO)
    logger.addFilter(RequestIdFilter())
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] [req:%(request_id)s] %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    try:
        LOG_DIR.mkdir(exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "kvoc.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError:
        # a read-only filesystem (some hosting platforms) shouldn't take the
        # whole app down over log files - console logging above still works
        logger.warning("could not open logs/kvoc.log for writing - logging to console only")

    return logger


# To switch to Sentry later instead of (or alongside) this: `pip install
# sentry-sdk`, then near the top of app/main.py:
#     import sentry_sdk
#     sentry_sdk.init(dsn=os.environ["KVOC_SENTRY_DSN"])
# Sentry's FastAPI integration picks up unhandled exceptions on its own -
# the register_error_logging() handler in app/main.py below would keep
# working alongside it unmodified.
