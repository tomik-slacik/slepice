"""Convenience entry point: `python run.py`

Respects HOST/PORT/KVOC_RELOAD env vars if set, so the same entry point
works both for local dev (defaults: 127.0.0.1:8000, auto-reload on) and
inside a deployed container, where the platform assigns $PORT and
auto-reload should be off - see Dockerfile and docs/DEPLOYMENT.md.
"""
import os

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("KVOC_RELOAD", "1") not in ("0", "false", "False")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
