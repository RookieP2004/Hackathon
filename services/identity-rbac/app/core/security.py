"""
Password hashing, JWT access tokens, and opaque refresh/reset token generation.

ARCHITECTURE.md §20.1: short-lived JWT access tokens (5-15 min) validated at
the API Gateway on every request; refresh tokens are opaque random strings,
never JWTs themselves, hashed at rest (aegis_db.models.auth.RefreshToken) so a
stolen database dump doesn't hand an attacker usable tokens.

Password hashing uses the `bcrypt` package directly, not passlib's bcrypt
wrapper. passlib (unmaintained since 2020) probes a `bcrypt.__about__` module
at import/first-use time that modern bcrypt (4.1+) no longer ships, raising
`AttributeError`/`ValueError` on every hash/verify call -- confirmed by
actually running this code, not a hypothetical concern. bcrypt's own API is a
thin, actively maintained two-function surface, so passlib buys nothing here.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

# bcrypt truncates its own input at 72 bytes -- encode explicitly and slice
# before hashing so a >72-byte password fails predictably at verification
# time (matching what was hashed) rather than bcrypt silently truncating a
# differently-encoded byte string during verify and producing a confusing
# false rejection.
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    truncated = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    try:
        return bcrypt.checkpw(truncated, password_hash.encode("utf-8"))
    except ValueError:
        # Malformed/foreign hash format (e.g. a pre-migration hash from a
        # different scheme) -- reject rather than raise, so a bad stored hash
        # can never be mistaken for a server error that leaks information.
        return False


def create_access_token(*, user_id: int, role_id: int, extra_claims: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    claims = {
        "sub": str(user_id),
        "role_id": role_id,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


def generate_opaque_token() -> tuple[str, str]:
    """
    Returns (raw_token, token_hash). The raw token is what's sent to the client
    once, at issuance; only the hash is ever persisted (aegis_db's
    RefreshToken/PasswordResetToken.token_hash) — matching those models'
    documented "never store the raw secret" contract.
    """
    raw = secrets.token_urlsafe(48)
    return raw, hash_opaque_token(raw)


def hash_opaque_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
