"""Project-independent, read-only OpenCode catalog discovery.

Never use workspace credentials or return the shared OpenCode daemon's
connection state. Provider policy must be applied by the requesting route.
"""
import threading
import time

from fastapi import HTTPException

from ..config import settings
from .opencode import OpenCodeService


_catalog_lock = threading.Lock()
_catalog_cache = {}
CATALOG_TTL_SECONDS = 30.0


def public_catalog(path, *, agents=False):
    """Read one native OpenCode catalog with a bounded loopback HTTP client."""
    if path not in {"/provider", "/agent"}:
        raise ValueError("Unsupported public catalog path")
    if agents != (path == "/agent"):
        raise ValueError("Catalog type must match the requested OpenCode endpoint")
    with _catalog_lock:
        cached = _catalog_cache.get(path)
        if cached and time.monotonic() - cached[0] < CATALOG_TTL_SECONDS:
            return cached[1]
        service = OpenCodeService(settings.opencode_url)
        try:
            data = service.request("GET", path)
            if agents:
                if not isinstance(data, list):
                    raise HTTPException(502, "OpenCode returned an invalid agent catalog")
                # Only public built-in-looking agent choice metadata; do not
                # cache runtime config, private prompts or tools.
                public = [{"name": row["name"], "mode": row.get("mode"), "hidden": row.get("hidden", False)}
                          for row in data if isinstance(row, dict)
                          and isinstance(row.get("name"), str) and 0 < len(row["name"]) <= 120]
            else:
                if not isinstance(data, dict) or not isinstance(data.get("all"), list):
                    raise HTTPException(502, "OpenCode returned an invalid provider catalog")
                # Copy only the public identifiers required by index/search.
                public = {"all": [{"id": item["id"], "name": item.get("name", item["id"]),
                                   "models": {k: None for k in item.get("models", {})}}
                                  for item in data["all"] if isinstance(item, dict)
                                  and isinstance(item.get("id"), str)
                                  and isinstance(item.get("models", {}), dict)],
                          "connected": [], "gateway_disconnected": [],
                          "default": data.get("default", {})}
            _catalog_cache[path] = (time.monotonic(), public)
            return public
        finally:
            service.close()
