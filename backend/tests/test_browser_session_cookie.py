"""Session-cookie contract, not proof of Android browser-restoration behavior."""
import os
from types import SimpleNamespace
from unittest.mock import Mock
from http.cookies import SimpleCookie
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from fastapi import Response
from backend.app.routes import auth
from backend.app.config import settings


def test_normal_signin_uses_nonpersistent_httponly_cookie():
    response=Response();db=Mock()
    auth.set_session(response,db,SimpleNamespace(id='owned',status='active',password_hash='hashed'))
    values=response.headers.getlist('set-cookie');cookie=SimpleCookie();cookie.load(values[0]);item=cookie[settings.session_cookie_name]
    assert item['max-age']=='' and item['expires']==''
    assert item['httponly'] and item['samesite']=='strict' and item['path']=='/'
    assert bool(item['secure'])==settings.cookie_secure
    assert 'X-Session-Idle-Expires-At' in response.headers
    stored=db.add.call_args.args[0]
    assert item.value!=stored.token_hash
    db.commit.assert_called_once()


def test_explicit_logout_revokes_cookie_and_record():
    response=Response();record=SimpleNamespace(revoked_at=None);db=Mock();db.scalar.return_value=record
    auth.logout(SimpleNamespace(cookies={settings.session_cookie_name:'disposable-test-token'}),response,db)
    assert record.revoked_at is not None
    cookie=SimpleCookie();cookie.load(response.headers.getlist('set-cookie')[0]);assert cookie[settings.session_cookie_name]['max-age']=='0'
    db.commit.assert_called_once()


def idle_fixture(seconds):
    from datetime import datetime, timezone, timedelta
    now=datetime.now(timezone.utc)
    user=SimpleNamespace(id='owned',status='active',password_hash='hashed',role='customer')
    record=SimpleNamespace(id='session',user=user,revoked_at=None,last_seen_at=now-timedelta(seconds=seconds),created_at=now-timedelta(days=1),expires_at=now+timedelta(days=1))
    request=SimpleNamespace(cookies={settings.session_cookie_name:'test-only'},state=SimpleNamespace(),url=SimpleNamespace(path='/api/auth/me'))
    db=Mock();db.scalar.return_value=record
    return request,db,record,user


def test_polling_does_not_extend_idle_deadline():
    from backend.app.routes.dependencies import require_user
    request,db,record,user=idle_fixture(899)
    seen=record.last_seen_at
    assert require_user(request,db) is user
    assert record.last_seen_at==seen
    db.commit.assert_not_called()


def test_fifteen_minutes_idle_revokes_session():
    import pytest
    from fastapi import HTTPException
    from backend.app.routes.dependencies import require_user
    request,db,record,user=idle_fixture(900)
    with pytest.raises(HTTPException) as error: require_user(request,db)
    assert error.value.status_code==401 and record.revoked_at is not None
    db.commit.assert_called_once()


def test_delayed_activity_cannot_revive_expired_session():
    import pytest
    from fastapi import HTTPException
    request,db,record,user=idle_fixture(901);request.state.auth_session=record;seen=record.last_seen_at
    with pytest.raises(HTTPException) as error: auth.activity(request,None,user,db)
    assert error.value.status_code==401 and record.last_seen_at==seen
    assert record.revoked_at is not None


def test_only_explicit_activity_extends_valid_session():
    request,db,record,user=idle_fixture(100);request.state.auth_session=record;seen=record.last_seen_at
    result=auth.activity(request,None,user,db)
    assert record.last_seen_at>seen and 'idle_expires_at' in result
