"""Persistent preview lease schema (not active until Alembic migration).

Preview state is independent of OpenCode agent sessions and authentication.
A lease stores allocation identity, never provider credentials or project files.
"""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class PreviewRuntimeLease(Base):
    __tablename__ = "preview_runtime_leases"
    __table_args__ = (
        CheckConstraint("state IN ('queued','starting','running','stopped','failed','expired')", name="ck_preview_lease_state"),
        Index("ix_preview_lease_state_seen", "state", "last_user_activity_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(20), default="stopped", nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pool_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_revision: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_user_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
