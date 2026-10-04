import json
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    price_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    duration_days: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PlatformPolicy(Base):
    """Single-row platform policy. Lists are stored as JSON text."""
    __tablename__ = "platform_policy"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    allowed_providers: Mapped[str] = mapped_column(Text, default="[]")
    allowed_models: Mapped[str] = mapped_column(Text, default="[]")
    allowed_tools: Mapped[str] = mapped_column(Text, default="[]")
    require_tool_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def as_payload(self):
        def load(value):
            try:
                return json.loads(value or "[]")
            except ValueError:
                return []
        return {
            "allowed_providers": load(self.allowed_providers),
            "allowed_models": load(self.allowed_models),
            "allowed_tools": load(self.allowed_tools),
            "require_tool_approval": bool(self.require_tool_approval),
            "updated_at": self.updated_at,
        }

def get_policy(db) -> PlatformPolicy:
    row = db.get(PlatformPolicy, 1)
    if row is None:
        row = PlatformPolicy(id=1, allowed_providers="[]", allowed_models="[]", allowed_tools="[]", require_tool_approval=True)
        db.add(row)
        db.commit()
    return row
