"""Focused regression checks for trial and signup access policy.

Run with: pytest -q backend/tests/test_signup_entitlement_contracts.py
Requires the backend's Python dependencies; does not connect to PostgreSQL or SMTP.
"""
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")

from backend.app.services.disposable_email import require_permanent_email
from backend.app.services.entitlements import access_payload


def _user(now):
    return SimpleNamespace(
        id="fake-user", role="customer", trial_started_at=now-timedelta(days=2),
        trial_ends_at=now+timedelta(days=28), advanced_trial_started_at=None,
        created_at=now-timedelta(days=2))


def _subscription(now, status="active", end_days=30):
    return SimpleNamespace(plan_id=12, status=status, started_at=now,
                           current_period_end=now+timedelta(days=end_days))


def test_temporary_addresses_are_rejected():
    for address in ("test@mailinator.com", "test@yopmail.com", "test@guerrillamail.com"):
        with pytest.raises(HTTPException) as exc:
            require_permanent_email(address)
        assert exc.value.status_code == 422


def test_normal_addresses_remain_allowed():
    require_permanent_email("person@gmail.com")
    require_permanent_email("staff@example.org")


def test_only_one_trial_including_advanced_features():
    now = datetime.now(timezone.utc)
    db = Mock()
    db.scalar.return_value = None
    value = access_payload(db, _user(now), now=now)
    assert value["core_trial"]["active"] is True
    assert value["advanced_integrations"] is True
    assert value["advanced_trial"]["state"] == "disabled"


def test_paid_access_has_independent_countdown():
    now = datetime.now(timezone.utc)
    db = Mock()
    db.scalar.side_effect = [_subscription(now), "verified-order"]
    value = access_payload(db, _user(now), now=now)
    assert value["reason"] == "subscription"
    assert value["paid_access"]["remaining_days"] == 30
    assert value["core_trial"]["active"] is False


def test_expired_paid_period_does_not_reopen_trial():
    now = datetime.now(timezone.utc)
    db = Mock()
    db.scalar.side_effect = [_subscription(now, end_days=-1), "verified-order"]
    value = access_payload(db, _user(now), now=now)
    assert value["allowed"] is False
    assert value["reason"] == "subscription_required"
    assert value["core_trial"]["active"] is False
    assert value["core_trial"]["remaining_days"] == 0
