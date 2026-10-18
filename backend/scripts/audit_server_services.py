#!/usr/bin/env python3
"""Read-only Ubuntu service inventory. NEVER terminates processes/services.

Classification is advisory: zero connections or low CPU is NOT proof of idle.
"""
import subprocess

PROTECTED = ("ssh", "nginx", "postgresql", "systemd", "docker", "containerd",
             "opencode-gateway", "opencode-web", "network", "dbus", "cron")


def inventory():
    command = ["systemctl", "list-units", "--type=service", "--state=running",
               "--no-legend", "--plain", "--no-pager"]
    output = subprocess.run(command, capture_output=True, text=True, check=True, timeout=10).stdout
    for line in output.splitlines():
        unit = line.split(maxsplit=1)[0] if line.strip() else ""
        if not unit.endswith(".service"):
            continue
        protected = any(unit.startswith(name) for name in PROTECTED)
        yield unit, "PROTECTED / REVIEW ONLY" if protected else "REVIEW MANUALLY"


if __name__ == "__main__":
    print("READ-ONLY: never stop a unit just because it appears idle")
    for unit, category in inventory():
        print(f"{unit:48} {category}")
