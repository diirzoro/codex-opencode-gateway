"""Internal policy boundaries, controlled time; no email/payment processing."""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from backend.app.services import customer_lifecycle as lifecycle, entitlements

NOW=datetime(2026,10,14,tzinfo=timezone.utc)

def user(end):
    return SimpleNamespace(id='fixture',role='customer',trial_started_at=end-timedelta(days=30),trial_ends_at=end)

@pytest.mark.parametrize('delta,allowed',[(1,True),(0,False),(-1,False)])
def test_trial_exact_expiry(delta,allowed,monkeypatch):
    monkeypatch.setattr(lifecycle,'_policy_started',None)
    db=Mock();db.scalar.side_effect=[None,None]
    result=entitlements.access_payload(db,user(NOW+timedelta(seconds=delta)),now=NOW)
    assert result['allowed'] is allowed
    assert result['advanced_trial']['state']=='disabled'
    assert result['account_retention']['minimum_days']==90


def test_paid_history_prevents_return_to_unused_trial(monkeypatch):
    monkeypatch.setattr(lifecycle,'_policy_started',None)
    paid=SimpleNamespace(plan_id=1,status='expired',current_period_end=NOW-timedelta(days=1))
    db=Mock();db.scalar.side_effect=[paid,'confirmed-payment-id']
    result=entitlements.access_payload(db,user(NOW+timedelta(days=20)),now=NOW)
    assert result['allowed'] is False and result['core_trial']['active'] is False
    assert result['core_trial']['remaining_days']==0 and result['kind']=='subscription'


def test_retention_uses_paid_expiry_and_preserves_policy_grace(monkeypatch):
    trial=user(NOW+timedelta(days=20))
    paid=SimpleNamespace(plan_id=1,status='expired',current_period_end=NOW-timedelta(days=10))
    monkeypatch.setattr(lifecycle,'_policy_started',None)
    assert lifecycle.archive_deadline(trial,paid)==NOW+timedelta(days=80)
    monkeypatch.setattr(lifecycle,'_policy_started',NOW)
    assert lifecycle.archive_deadline(trial,paid)==NOW+timedelta(days=90)
