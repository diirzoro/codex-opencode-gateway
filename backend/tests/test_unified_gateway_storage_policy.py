"""Shared Gateway storage tier regressions (no VPS, GitHub OAuth, payment or AI calls)."""
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")

from backend.app.models import Plan, User
from backend.app.services import storage_policy, workspaces


def fake_db(*, code="gateway_100", paid=True, active=True, role="customer"):
    db = Mock()
    user = NS(id="account-a", role=role)
    plan = NS(code=code)
    current = NS(status="active" if active else "trial", plan_id=1,
                 current_period_end=datetime.now(timezone.utc)+timedelta(days=8))
    db.get.side_effect = lambda model, identifier: user if model is User else plan if model is Plan else None
    db.scalar.side_effect = [current, "verified-payment" if paid else None]
    return db


@pytest.mark.parametrize("code,amount",[
    ("gateway_100",100),("gateway_150",150),("gateway_250",250),
    ("monthly",100),("two_months",150),("three_months",250)])
def test_verified_subscription_grants_a_single_storage_quota(code,amount):
    assert storage_policy.quota_mb(fake_db(code=code), "account-a") == amount


@pytest.mark.parametrize("paid,active",[(False,True),(True,False),(False,False)])
def test_no_paid_entitlement_cannot_raise_trial_storage(paid,active):
    assert storage_policy.quota_mb(fake_db(paid=paid,active=active), "account-a") == 50


def test_owner_has_one_bounded_quota():
    assert storage_policy.quota_mb(fake_db(role="owner"),"account-a") == 250


def test_local_and_github_workspaces_share_one_account_sum(monkeypatch):
    rows=[NS(project=NS(source_type="blank"),size=4*storage_policy.MIB),
          NS(project=NS(source_type="github"),size=7*storage_policy.MIB),
          NS(project=NS(source_type="template"),size=9*storage_policy.MIB)]
    db=Mock()
    db.scalars.return_value=rows
    monkeypatch.setattr(workspaces,"usage_bytes",lambda workspace,stop_at=None: workspace.size)
    assert workspaces.account_storage_parts(db,"account-a")==(
        13*storage_policy.MIB,7*storage_policy.MIB)
    assert workspaces.account_storage(db,"account-a")==20*storage_policy.MIB


def test_both_project_types_display_exactly_the_same_owner_total(monkeypatch):
    monkeypatch.setattr(workspaces,"account_storage_parts",lambda db,id,stop_at=None:(5*storage_policy.MIB,9*storage_policy.MIB))
    monkeypatch.setattr(storage_policy,"quota_mb",lambda db,id:100)
    monkeypatch.setattr(workspaces,"usage_bytes",lambda row,stop_at=None:row.size)
    from backend.app.services import workspace_cache
    monkeypatch.setattr(workspace_cache,"cache_payload",lambda row:{"retention_hours":73})
    db=Mock()
    local=NS(user_id="owner",project=NS(source_type="blank"),size=5*storage_policy.MIB)
    github=NS(user_id="owner",project=NS(source_type="github"),size=9*storage_policy.MIB)
    a=workspaces.storage_payload(local,db)
    b=workspaces.storage_payload(github,db)
    for field in ("used_bytes","limit_bytes","remaining_bytes","used_mb","limit_mb","scope","local_used_mb","github_used_mb"):
        assert a[field]==b[field],field
    assert a["used_mb"]==14 and a["limit_mb"]==100
    assert a["workspace_used_mb"]==5 and b["workspace_used_mb"]==9
    assert a["scope"]=="account_all_projects"


def test_shared_quota_413_preserves_files_and_payment_state(monkeypatch):
    db=fake_db()
    monkeypatch.setattr(workspaces,"account_storage",lambda db,user_id,stop_at=None:99*storage_policy.MIB)
    with pytest.raises(HTTPException) as exc:
        storage_policy.require_headroom(db,"account-a",additional=2*storage_policy.MIB)
    assert exc.value.status_code==413
    assert "local and imported GitHub" in exc.value.detail
    assert db.commit.call_count==0
