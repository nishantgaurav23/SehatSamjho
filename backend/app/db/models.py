"""S2.3 — Interaction Log Table.

Defines the interaction_log PostgreSQL table for pipeline analytics.
Zero PHI: only metadata (phone_hash, language, doc_type, latency, status).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class InteractionStatus(str, enum.Enum):
    """Pipeline interaction outcome status."""

    SUCCESS = "success"
    ERROR = "error"
    FLAGGED = "flagged"


class InteractionLog(Base):
    """Metadata log for each prescription-translation pipeline run.

    Zero PHI: raw phone numbers are SHA-256 hashed; no image content
    or extracted/translated text is ever persisted.
    """

    __tablename__ = "interaction_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    language_code: Mapped[str] = mapped_column(String(10), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False, default="prescription")
    confidence_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<InteractionLog id={self.id} status={self.status} lang={self.language_code}>"
