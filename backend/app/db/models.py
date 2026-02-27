"""
PostgreSQL ORM table definitions for SehatSamjho.

Tables:
    TranslationLog — one row per completed patient interaction.
                     Metadata only, zero PHI stored.

Privacy guarantees:
    - phone_hash : SHA-256 of the user's phone number — not reversible.
    - No prescription text, patient name, doctor name, or diagnosis stored.

Integration:
    Base              ← app/db/database.py   (Alembic reads Base.metadata)
    TranslationLog    → written by api/webhooks.py after each interaction
                      → read by api/dashboard.py for B2B analytics
"""

import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class TranslationLog(Base):
    """One metadata row per patient interaction. Zero PHI."""

    __tablename__ = "translation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    # Twilio MessageSid — unique per message, used for idempotency
    request_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    # SHA-256 of phone number — unique-user counts without storing PHI
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    language_code: Mapped[str] = mapped_column(String(10), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Average extraction confidence score (0.0–1.0) from GPT-4o Vision.
    # NULL when the request errored out before extraction completed.
    confidence_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    drug_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_audio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
