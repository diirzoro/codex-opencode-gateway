"""Read-only package-manager identification for isolated Preview preparation.

Never execute scripts, install dependencies, or trust a manifest command.
Ambiguous lockfiles deliberately block automatic preparation.
"""
from __future__ import annotations

from pathlib import Path

LOCKFILES = {
    "npm": "package-lock.json",
    "pnpm": "pnpm-lock.yaml",
    "yarn": "yarn.lock",
    "bun": "bun.lock",
}
BUN_ALTERNATE = "bun.lockb"


def detect(root: Path) -> dict[str, object]:
    """Inspect regular root-level lockfiles and return an advisory build plan."""
    root = Path(root)
    manifest = root / "package.json"
    if not manifest.is_file() or manifest.is_symlink():
        return {"package_manager": None, "lockfiles": [], "installation_ready": False,
                "reason": "No safe root package.json"}
    found = []
    for manager, filename in LOCKFILES.items():
        candidate = root / filename
        if candidate.is_file() and not candidate.is_symlink():
            found.append((manager, filename))
    legacy = root / BUN_ALTERNATE
    if legacy.is_file() and not legacy.is_symlink():
        found.append(("bun", BUN_ALTERNATE))
    managers = {manager for manager, _ in found}
    if not found:
        reason = "No lockfile; automatic dependency installation is disabled"
    elif len(found) != 1 or len(managers) != 1:
        reason = "Ambiguous package-manager lockfiles; select a supported lockfile"
    else:
        reason = "Ready for isolated preparation only; worker not yet configured"
    selected = found[0][0] if len(found) == 1 else None
    return {
        "package_manager": selected,
        "lockfiles": [name for _, name in found],
        "installation_ready": len(found) == 1,
        "reason": reason,
    }
