"""
Authentication & authorisation helpers.

Supports two authentication strategies:
  1. JWT bearer tokens (for interactive users)
  2. Static API keys (for machine-to-machine integration)

Both resolve to a *CurrentUser* context object that downstream code can
depend on without caring which auth method was used.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import Settings, get_settings

# ── Password hashing ────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── FastAPI security schemes ────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


class CurrentUser(BaseModel):
    """Resolved identity that request handlers receive."""
    user_id: str
    project_id: str
    is_admin: bool = False


# ── JWT helpers ─────────────────────────────────────────────

def create_access_token(
    data: dict,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = settings or get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


# ── API-key helpers ─────────────────────────────────────────

def generate_api_key() -> str:
    """Return a fresh random 48-char API key."""
    return secrets.token_urlsafe(36)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ── Dependency: resolve current user from request ───────────

async def get_current_user(
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """
    Try JWT first, fall back to API key.
    Returns a *CurrentUser* or raises 401.
    """
    # --- JWT path ---
    if bearer is not None:
        try:
            payload = decode_access_token(bearer.credentials, settings)
            return CurrentUser(
                user_id=payload["sub"],
                project_id=payload.get("project_id", "default"),
                is_admin=payload.get("is_admin", False),
            )
        except (JWTError, KeyError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired JWT token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # --- API-key path ---
    if api_key is not None:
        # In production this would look up the hashed key in the DB.
        # For now we accept any non-empty key and derive an identity.
        key_hash = hash_api_key(api_key)
        return CurrentUser(
            user_id=f"apikey-{key_hash[:12]}",
            project_id="default",
            is_admin=False,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
