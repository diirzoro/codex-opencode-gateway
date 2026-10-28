"""Verified GitHub identity history, never a credential or ownership store."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class GithubIdentityRegistry(Base):
    __tablename__ = 'github_identity_registry'
    __table_args__ = (CheckConstraint('github_user_id > 0', name='ck_github_registry_positive_id'),)
    github_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    primary_email_hmac: Mapped[str] = mapped_column(String(64))
    first_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    retain_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc)+timedelta(days=90), index=True)
    verification_status: Mapped[str] = mapped_column(String(30), default='verified')
