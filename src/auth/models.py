"""
src/auth/models.py
==================
SQLAlchemy ORM models and engine/session factory for the auth + history layer.

Database selection is driven entirely by ``settings.database_url``:

* ``DATABASE_URL`` set to a Postgres URL  -> production multi-user Postgres
* unset                                   -> local ``sqlite:///data/users.db``

The same models work on both, so development and production stay identical.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """A registered application user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # Format: "pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>" — never the raw password.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    analyses: Mapped[list["SavedAnalysis"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="SavedAnalysis.created_at.desc()",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id} username={self.username!r}>"


class SavedAnalysis(Base):
    """A snapshot of one analysis a user ran, for their history view."""

    __tablename__ = "saved_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(128), default="")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[str] = mapped_column(String(32), default="")
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    executive_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    user: Mapped["User"] = relationship(back_populates="analyses")


# --------------------------------------------------------------------------- #
# Engine / session factory (singletons, created lazily)
# --------------------------------------------------------------------------- #
_engine = None
_SessionLocal: sessionmaker | None = None


def _build_engine():
    url = settings.normalized_database_url
    if url.startswith("sqlite"):
        # SQLite needs this flag to be used across Streamlit's threads.
        return create_engine(
            url, connect_args={"check_same_thread": False}, pool_pre_ping=True
        )
    return create_engine(url, pool_pre_ping=True)


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False
        )
    return _SessionLocal


def init_auth_db() -> None:
    """Create the auth/history tables if they do not yet exist."""
    Base.metadata.create_all(get_engine())
