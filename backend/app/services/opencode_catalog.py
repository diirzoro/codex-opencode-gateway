"""Project-independent, read-only OpenCode catalog discovery.

Never use workspace credentials or return the shared OpenCode daemon's
connection state. Provider policy must be applied by the requesting route.
"""
from fastapi import HTTPException

from ..config import settings
from .opencode import OpenCodeService


def public_catalog(path, *, agents=False):
    """Read one native OpenCode catalog with a bounded loopback HTTP client."""
    if path not in {"/provider", "/agent"}:
        raise ValueError("Unsupported public catalog path")
    service = OpenCodeService(settings.opencode_url)
    try:
        data = service.request("GET", path)
        if agents:
            if not isinstance(data, list):
                raise HTTPException(502, "OpenCode returned an invalid agent catalog")
        elif not isinstance(data, dict) or not isinstance(data.get("all"), list):
            raise HTTPException(502, "OpenCode returned an invalid provider catalog")
        return data if agents else {**data, "connected": [], "gateway_disconnected": []}
    finally:
        service.close()
