"""
src/auth/service.py
===================
Authentication business logic: registration, login, password hashing, and
signed session tokens — plus saving/listing a user's analysis history.

Security notes
--------------
* Passwords are never stored in clear text. We use PBKDF2-HMAC-SHA256 with a
  per-user random salt (Python stdlib only — no external crypto dependency),
  and compare hashes in constant time.
* Session tokens are HMAC-SHA256 signed (keyed by ``settings.secret_key``) and
  carry an expiry, so a token copied from the URL cannot be forged or replayed
  forever. The token is opaque to the browser and verified server-side.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config import settings
from src.auth.models import SavedAnalysis, User, get_sessionmaker, init_auth_db

_PBKDF2_ROUNDS = 240_000
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    """Raised for any expected authentication failure (bad input, dupes, etc.)."""


@dataclass
class SavedAnalysisDTO:
    """A detached, render-safe view of a saved analysis row."""

    id: int
    ticker: str
    company_name: str
    price: Optional[float]
    rating: str
    final_score: Optional[float]
    confidence: Optional[int]
    executive_summary: str
    created_at: str


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Return a self-describing PBKDF2 hash string for *password*."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verify *password* against a stored PBKDF2 hash string."""
    try:
        algorithm, rounds_s, salt_hex, hash_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(candidate, expected)


# --------------------------------------------------------------------------- #
# Registration / login
# --------------------------------------------------------------------------- #
def _validate_registration(username: str, email: str, password: str) -> None:
    if not _USERNAME_RE.match(username):
        raise AuthError(
            "Username must be 3-32 characters: letters, numbers, or underscores."
        )
    if not _EMAIL_RE.match(email):
        raise AuthError("Please enter a valid email address.")
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters long.")


def register_user(username: str, email: str, password: str) -> User:
    """Create a new user. Raises :class:`AuthError` on any validation issue."""
    init_auth_db()
    username = (username or "").strip()
    email = (email or "").strip().lower()
    _validate_registration(username, email, password)

    Session = get_sessionmaker()
    with Session() as session:
        existing = session.scalar(
            select(User).where((User.username == username) | (User.email == email))
        )
        if existing is not None:
            if existing.username == username:
                raise AuthError("That username is already taken.")
            raise AuthError("An account with that email already exists.")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise AuthError("That username or email is already registered.")
        session.refresh(user)
        return user


def authenticate_user(identifier: str, password: str) -> User:
    """Authenticate by username OR email + password. Raises on failure."""
    init_auth_db()
    identifier = (identifier or "").strip()
    if not identifier or not password:
        raise AuthError("Please enter your credentials.")

    Session = get_sessionmaker()
    with Session() as session:
        lowered = identifier.lower()
        user = session.scalar(
            select(User).where(
                (User.username == identifier) | (User.email == lowered)
            )
        )
        # Always run the hash to keep timing uniform whether or not the user exists.
        stored = user.password_hash if user else hash_password("dummy-timing-guard")
        if not verify_password(password, stored) or user is None:
            raise AuthError("Invalid username/email or password.")
        return user


def get_user_by_id(user_id: int) -> Optional[User]:
    init_auth_db()
    Session = get_sessionmaker()
    with Session() as session:
        return session.get(User, user_id)


# --------------------------------------------------------------------------- #
# Signed session tokens (survive a browser refresh via URL query params)
# --------------------------------------------------------------------------- #
def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(payload_b64: str) -> str:
    sig = hmac.new(
        settings.secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    return _b64e(sig)


def issue_session_token(user: User) -> str:
    """Return a signed, expiring token encoding the user id."""
    payload = {
        "uid": user.id,
        "u": user.username,
        "exp": int(time.time()) + settings.session_ttl_hours * 3600,
        "nonce": secrets.token_hex(4),
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_session_token(token: str) -> Optional[int]:
    """Return the user id if *token* is valid and unexpired, else ``None``."""
    if not token or "." not in token:
        return None
    payload_b64, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(payload_b64)):
        return None
    try:
        payload = json.loads(_b64d(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return int(payload.get("uid", 0)) or None


# --------------------------------------------------------------------------- #
# Saved analysis history
# --------------------------------------------------------------------------- #
def save_analysis(
    *,
    user_id: int,
    ticker: str,
    company_name: str,
    price: Optional[float],
    rating: str,
    final_score: Optional[float],
    confidence: Optional[int],
    executive_summary: str,
) -> int:
    """Persist one analysis snapshot for a user; returns the new row id."""
    init_auth_db()
    Session = get_sessionmaker()
    with Session() as session:
        row = SavedAnalysis(
            user_id=user_id,
            ticker=ticker.upper(),
            company_name=company_name or "",
            price=price,
            rating=rating or "",
            final_score=final_score,
            confidence=confidence,
            executive_summary=(executive_summary or "")[:2000],
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def _to_dto(row: SavedAnalysis) -> SavedAnalysisDTO:
    return SavedAnalysisDTO(
        id=row.id,
        ticker=row.ticker,
        company_name=row.company_name,
        price=row.price,
        rating=row.rating,
        final_score=row.final_score,
        confidence=row.confidence,
        executive_summary=row.executive_summary,
        created_at=row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else "",
    )


def list_saved_analyses(user_id: int, limit: int = 25) -> list[SavedAnalysisDTO]:
    """Return a user's most recent saved analyses as detached DTOs."""
    init_auth_db()
    Session = get_sessionmaker()
    with Session() as session:
        rows = session.scalars(
            select(SavedAnalysis)
            .where(SavedAnalysis.user_id == user_id)
            .order_by(SavedAnalysis.created_at.desc())
            .limit(limit)
        ).all()
        return [_to_dto(r) for r in rows]


def delete_saved_analysis(user_id: int, analysis_id: int) -> bool:
    """Delete one of the user's saved analyses. Returns True if a row was removed."""
    init_auth_db()
    Session = get_sessionmaker()
    with Session() as session:
        row = session.get(SavedAnalysis, analysis_id)
        if row is None or row.user_id != user_id:
            return False
        session.delete(row)
        session.commit()
        return True
