"""Password hashing and JWT session tokens.

No third-party identity service involved - accounts live entirely in this
app's own database (bcrypt-hashed passwords, never plaintext). This is
separate from, and has nothing to do with, the "never enter a user's
password into a service" rule that governs an *agent* acting on someone's
behalf elsewhere - this module is the app's own auth system, the same kind
of code any backend needs.
"""
from __future__ import annotations

import datetime as dt
import secrets
from collections import defaultdict
from typing import Dict, List

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

# ---- login rate limiting (see config.LOGIN_MAX_ATTEMPTS/LOGIN_LOCKOUT_MINUTES) ----
# in-memory, per-process - see the caveat on config.py's LOGIN_MAX_ATTEMPTS
_failed_logins: Dict[str, List[dt.datetime]] = defaultdict(list)


def check_login_not_locked_out(email: str) -> None:
    key = email.lower()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=config.LOGIN_LOCKOUT_MINUTES)
    _failed_logins[key] = [t for t in _failed_logins[key] if t > cutoff]
    if len(_failed_logins[key]) >= config.LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"too many failed login attempts - try again in {config.LOGIN_LOCKOUT_MINUTES} minutes",
        )


def record_failed_login(email: str) -> None:
    _failed_logins[email.lower()].append(dt.datetime.now(dt.timezone.utc))


def clear_failed_logins(email: str) -> None:
    _failed_logins.pop(email.lower(), None)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + dt.timedelta(days=config.JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def _decode_token(token: str) -> int:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = _decode_token(token)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def require_admin(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> None:
    """Two independent ways in, see config.ADMIN_TOKEN's docstring: a
    shared X-Admin-Token header, or a logged-in user with is_admin=True.
    Neither is accepted if KVOC_ADMIN_TOKEN was never set AND no token was
    presented - admin endpoints are refused outright, not "open by default".
    """
    if x_admin_token and config.ADMIN_TOKEN and x_admin_token == config.ADMIN_TOKEN:
        return
    if token:
        try:
            user = db.get(User, _decode_token(token))
        except HTTPException:
            user = None
        if user is not None and user.is_admin:
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin access required")
