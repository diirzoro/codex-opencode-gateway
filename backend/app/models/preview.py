"""Persistent preview lease schema (not active until Alembic migration).

Preview state is independent of OpenCode agent sessions and authentication.
A lease stores allocation identity, never provider credentials or project files.
"""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, Boolean, String, CheckConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class PreviewRuntimeLease(Base):
    __tablename__ = "preview_runtime_leases"
    __table_args__ = (
        CheckConstraint("state IN ('queued','starting','running','stopped','failed','expired')", name="ck_preview_lease_state"),
        Index("ix_preview_lease_state_seen", "state", "last_user_activity_at"),
        UniqueConstraint("workspace_id", name="uq_preview_lease_workspace"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
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


class PreviewWorkerCapacity(Base):
    """Trusted internal capacity registry, never populated by browser input."""
    __tablename__ = "preview_worker_capacities"
    worker_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    isolated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    security_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reachable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cpu_free_millicores: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_free_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    disk_free_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    active_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_jobs: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    isolation_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
