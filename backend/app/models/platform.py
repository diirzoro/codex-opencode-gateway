import json
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
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

class Subscription(Base):
    """Per-user subscription state. Payment activation is intentionally not simulated."""
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="trial")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PaymentOrder(Base):
    __tablename__ = 'payment_orders'
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'),index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey('plans.id'))
    method_id: Mapped[uuid.UUID|None] = mapped_column(ForeignKey('billing_methods.id',ondelete='SET NULL'),nullable=True)
    plan_name: Mapped[str] = mapped_column(String(120))
    method_label: Mapped[str] = mapped_column(String(100))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    duration_days: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30),default='awaiting_payment')
    payment_reference: Mapped[str|None] = mapped_column(String(200),nullable=True)
    provider_order_id: Mapped[str|None] = mapped_column(String(100),nullable=True,unique=True)
    provider_capture_id: Mapped[str|None] = mapped_column(String(100),nullable=True,unique=True)
    provider_environment: Mapped[str|None] = mapped_column(String(10),nullable=True)
    confirmation_reference: Mapped[str|None] = mapped_column(String(200),nullable=True)
    receipt_path: Mapped[str|None] = mapped_column(String(500),nullable=True)
    reject_reason: Mapped[str|None] = mapped_column(String(500),nullable=True)
    billing_note: Mapped[str|None] = mapped_column(String(500),nullable=True)
    sender_name: Mapped[str|None] = mapped_column(String(150),nullable=True)
    transfer_date: Mapped[str|None] = mapped_column(String(10),nullable=True)
    amount_sent_cents: Mapped[int|None] = mapped_column(Integer,nullable=True)
    sender_email: Mapped[str|None] = mapped_column(String(254),nullable=True)
    sender_bank: Mapped[str|None] = mapped_column(String(150),nullable=True)
    sender_account: Mapped[str|None] = mapped_column(String(200),nullable=True)
    payer_name: Mapped[str|None] = mapped_column(String(150),nullable=True)
    payer_email: Mapped[str|None] = mapped_column(String(254),nullable=True)
    payer_country: Mapped[str|None] = mapped_column(String(80),nullable=True)
    reviewed_by: Mapped[uuid.UUID|None] = mapped_column(ForeignKey('users.id'),nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    paid_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)

class HomepageItem(Base):
    """Admin-managed Landing homepage slider ("Homepage Content" / "Offers & Messages").

    One row per carousel item. English and Arabic copy are stored side by side so the
    public Landing page can serve the correct language without a second translation
    system. Media is either a sprite icon identifier or an uploaded raster image path.
    """
    __tablename__ = "homepage_items"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_type: Mapped[str] = mapped_column(String(30), default="platform")
    badge: Mapped[str | None] = mapped_column(String(20), nullable=True)
    title_en: Mapped[str] = mapped_column(String(200))
    title_ar: Mapped[str] = mapped_column(String(200))
    body_en: Mapped[str] = mapped_column(Text, default="")
    body_ar: Mapped[str] = mapped_column(Text, default="")
    cta_label_en: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cta_label_ar: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cta_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(60), nullable=True)
    media_kind: Mapped[str] = mapped_column(String(10), default="icon")
    media_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def as_payload(self) -> dict:
        return {
            "id": self.id,
            "item_type": self.item_type,
            "badge": self.badge,
            "title_en": self.title_en,
            "title_ar": self.title_ar,
            "body_en": self.body_en,
            "body_ar": self.body_ar,
            "cta_label_en": self.cta_label_en,
            "cta_label_ar": self.cta_label_ar,
            "cta_url": self.cta_url,
            "icon": self.icon,
            "media_kind": self.media_kind,
            "has_image": bool(self.media_path) and self.media_kind == "image",
            "image_url": f"/api/homepage/media/{self.id}" if (self.media_path and self.media_kind == "image") else None,
            "sort_order": self.sort_order,
            "enabled": bool(self.enabled),
            "pinned": bool(self.pinned),
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
        }

def get_policy(db) -> PlatformPolicy:
    row = db.get(PlatformPolicy, 1)
    if row is None:
        row = PlatformPolicy(id=1, allowed_providers="[]", allowed_models="[]", allowed_tools="[]", require_tool_approval=True)
        db.add(row)
        db.commit()
    return row
