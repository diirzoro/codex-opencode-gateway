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


def plan_pools(user_count: int, *, users_per_pool: int = DEFAULT_POOL_USERS) -> dict[str, object]:
    """Calculate logical pool demand only; never provision hosts or containers.

    Actual pool activation must be gated by measured capacity, security checks,
    and durable admission state. User count is NOT active runtime concurrency.
    """
    if isinstance(user_count, bool) or not isinstance(user_count, int) or user_count < 0:
        raise ValueError("user_count must be a nonnegative integer")
    if isinstance(users_per_pool, bool) or not isinstance(users_per_pool, int) or not 1 <= users_per_pool <= MAX_POOL_USERS:
        raise ValueError("users_per_pool must be between 1 and 100")
    requested = (user_count + users_per_pool - 1) // users_per_pool
    return {
        "registered_users": user_count,
        "users_per_pool": users_per_pool,
        "logical_pools_required": requested,
        "provisioned_pools": None,
        "worker_capacity_verified": False,
        "auto_provision_enabled": False,
        "note": "This plan does not allocate CPU, RAM, containers or sessions.",
    }
