"""Platform Native-mode flag only.

This module MUST NOT connect to OpenCode, proxy requests, create sessions,
query providers, inspect tools, patch permissions, or delete Native history.
OpenCode Native operations flow Browser -> Nginx -> OpenCode Native.
"""
import os

from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..models import User
from .dependencies import require_user

router = APIRouter(tags=["native-platform-state"])


def deployment():
    enabled_flags = {
        "test": os.getenv("OPENCODE_NATIVE_TEST_ENABLED", "").lower() in {"1", "true", "yes"},
        "live": os.getenv("OPENCODE_NATIVE_LIVE_ENABLED", "").lower() in {"1", "true", "yes"},
        "local": os.getenv("OPENCODE_NATIVE_LOCAL_ENABLED", "").lower() in {"1", "true", "yes"},
    }
    selected = [name for name, enabled in enabled_flags.items() if enabled]
    if len(selected) > 1:
        raise RuntimeError("Only one Native deployment mode may be enabled")
    if not selected:
        return None
    mode = selected[0]
    if mode != "local":
        expected_origin = ("https://test.opencode-gateway.codes" if mode == "test"
                           else "https://opencode-gateway.codes")
        expected_db = ("opencode_gateway_test" if mode == "test"
                       else "opencode_gateway")
        actual_db = settings.database_url.rsplit("/", 1)[-1].split("?", 1)[0]
        if settings.public_base_url.rstrip("/") != expected_origin or actual_db != expected_db:
            raise RuntimeError("Native deployment origin/database mismatch")
    return mode


def enabled():
    return deployment() is not None


def admit(_user):
    if not enabled():
        raise HTTPException(503, "Native mode is not enabled")


@router.get("/api/native-test/state")
def state(user: User = Depends(require_user)):
    """Platform-only configuration; does not call the Native daemon."""
    mode = deployment()
    if mode is None:
        return {"enabled": False}
    payload = {"enabled": True, "mode": "native-" + mode,
               "public_multi_user_ready": False}
    if mode == "local":
        # Administrative filesystem location, not a Native API query.
        account_root = settings.runtime_root / str(user.id) / "native-account"
        account_root.mkdir(parents=True, exist_ok=True)
        payload["native_account_directory"] = str(account_root)
    return payload
