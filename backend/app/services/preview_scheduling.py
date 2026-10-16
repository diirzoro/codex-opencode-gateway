"""Smart Preview classification and capacity policy. No user code execution.

This is scheduling metadata, NOT a worker allocator or security boundary.
Workers and admission decisions must be persisted and resource-aware separately.
"""

from __future__ import annotations

from typing import Mapping

DEFAULT_POOL_USERS = 50
MAX_POOL_USERS = 100
SOURCE_SNAPSHOT_MAX_BYTES = 50 * 1024 * 1024
DYNAMIC_IDLE_TIMEOUT_SECONDS = 5 * 60

_STATIC = frozenset({"html"})
_BUILD = frozenset({"vite", "react", "vue", "angular", "svelte"})
_DYNAMIC = frozenset({"node", "django", "python", "laravel", "php", "nuxt"})
_NEXT = frozenset({"nextjs"})


def classify(detected: Mapping[str, object]) -> dict[str, object]:
    """Produce a conservative preview strategy from read-only manifest detection.

    Framework recognition is not proof that a safe build profile exists.
    In particular Next.js can require SSR, so do not label it static.
    """
    framework = str(detected.get("framework", "unknown"))
    if framework in _STATIC:
        tier, action, runtime = "static", "serve_static", False
    elif framework in _BUILD:
        tier, action, runtime = "build", "isolated_build_required", False
    elif framework in _NEXT:
        tier, action, runtime = "conditional", "inspect_next_output_in_worker", True
    elif framework in _DYNAMIC:
        tier, action, runtime = "dynamic", "isolated_runtime_required", True
    else:
        tier, action, runtime = "unsupported", "diagnose", False
    return {
        "framework": framework,
        "resource_tier": tier,
        "strategy": action,
        "continuous_runtime_potentially_required": runtime,
        "consumes_dynamic_slot_now": False,
        "source_snapshot_max_bytes": SOURCE_SNAPSHOT_MAX_BYTES,
        "pool_target_users": DEFAULT_POOL_USERS,
        "pool_max_users": MAX_POOL_USERS,
        "dynamic_idle_timeout_seconds": DYNAMIC_IDLE_TIMEOUT_SECONDS,
        "idle_restart_requires_explicit_user_request": True,
        "capacity_note": (
            "Logical user counts do not reserve capacity. Build/runtime slots "
            "require measured CPU, RAM and secure worker availability."
        ),
    }


def idle_expired(*, last_activity_monotonic: float, now_monotonic: float) -> bool:
    """Check inactivity within a single worker process.

    The eventual durable lease/reaper must use persisted clock-safe timestamps;
    this helper is NOT a cross-restart lease implementation. Polling/status calls
    must never be recorded as genuine activity.
    """
    return now_monotonic - last_activity_monotonic >= DYNAMIC_IDLE_TIMEOUT_SECONDS
