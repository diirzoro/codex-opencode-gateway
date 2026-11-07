#!/usr/bin/env python3
"""Read-only Linux runtime audit for the OpenCode Gateway host.

This script NEVER stops or restarts a process. Run as the Gateway Unix user
to see local-process RSS, parents, cgroups and workspace identities. Process
age or apparent idleness alone is not evidence that it is safe to stop.
"""
import os
from pathlib import Path

TARGETS = ("opencode", "python")


def _read(path):
    try:
        return Path(path).read_text(errors="replace")
    except (OSError, PermissionError):
        return ""


def scan(proc=Path("/proc")):
    rows = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        cmd = _read(entry / "cmdline").replace("\0", " ").strip()
        if "opencode serve " not in cmd and "opencode web " not in cmd and "uvicorn app.main:app" not in cmd:
            continue
        status = _read(entry / "status")
        fields = {}
        for line in status.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fields[k] = v.strip()
        try:
            cwd = os.readlink(entry / "cwd")
        except OSError:
            cwd = "(inaccessible)"
        cgroup = _read(entry / "cgroup").strip()
        rows.append((pid, fields.get("PPid", "?"), fields.get("VmRSS", "?"), cwd, cgroup, cmd))
    return sorted(rows)


def main():
    print("READ-ONLY AUDIT: no process will be stopped or changed")
    for pid, parent, rss, cwd, cgroup, cmd in scan():
        kind = "TEST" if "-test" in cgroup or "-test" in cwd else "LIVE/OTHER"
        print(f"pid={pid} ppid={parent} rss={rss} environment={kind}")
        print(f"  cwd={cwd}")
        print(f"  cgroup={cgroup}")
        print(f"  cmd={cmd}")
    print("Never terminate based on RSS or age alone; check active agent jobs and ownership.")


if __name__ == "__main__":
    main()
