import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Integer, Text, func, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base

class Country(Base):
    __tablename__ = "countries"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    code: Mapped[str] = mapped_column(String(2), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class Region(Base):
    __tablename__ = "regions"
    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class City(Base):
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    username_identity: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True, index=True)
    email_identity: Mapped[str | None] = mapped_column(String(254), nullable=True, unique=True, index=True)
    phone_identity: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    github_subject: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    google_subject: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    phone: Mapped[str] = mapped_column(String(30))
    postal_code: Mapped[str] = mapped_column(String(24))
    country_id: Mapped[int | None] = mapped_column(ForeignKey("countries.id"), nullable=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), nullable=True)
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"), nullable=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="customer")
    status: Mapped[str] = mapped_column(String(20), default="active")
    preferred_language: Mapped[str] = mapped_column(String(5), default="ar")
    preferred_theme: Mapped[str] = mapped_column(String(10), default="light")
    trial_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    advanced_trial_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    country: Mapped[Country] = relationship()
    region: Mapped[Region | None] = relationship()
    city: Mapped[City | None] = relationship()
    plan = relationship("Plan", lazy="selectin")

class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship()


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_method: Mapped[str] = mapped_column(String(8), default="link", server_default="link")
    code_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PendingRegistration(Base):
    """Unverified signup attempt. NOT a user or an account."""
    __tablename__ = "pending_registrations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ticket_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    code_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sends: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())



@event.listens_for(User,'before_insert')
@event.listens_for(User,'before_update')
def synchronize_account_identities(mapper,connection,user):
    from ..security.identities import account_keys
    user.username_identity,user.email_identity,user.phone_identity=account_keys(user.username,user.email,user.phone,user.postal_code)
