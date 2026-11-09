#!/usr/bin/env python3
"""Explicit, destructive reset of experimental OpenCode Native provider auth.

Run via scripts/reset-native-provider-auth.sh (root). No key values are logged.
Does not modify Gateway PostgreSQL, subscriptions, activation, or billing.
"""
import os
import pwd
import re
import subprocess
import sys
from pathlib import Path

SERVICE = "opencode-native-test.service"
KEY_RE = re.compile(
    r"^(?:OPENAI|ANTHROPIC|DEEPSEEK|OPENROUTER|GEMINI|GOOGLE|MISTRAL|"
    r"COHERE|GROQ|TOGETHER|FIREWORKS|CEREBRAS|XAI|ZAI|MOONSHOT|KIMI|"
    r"PERPLEXITY|DASHSCOPE|SILICONFLOW|VOLCENGINE|MINIMAX|GLM|"
    r"DEEPINFRA|REPLICATE|AZURE_OPENAI|AWS_BEDROCK)_(?:.*_)?"
    r"(?:API_KEY|TOKEN|SECRET|ACCESS_KEY)$", re.I
)

def show(key):
    return subprocess.check_output(
        ["systemctl", "show", SERVICE, "-p", key, "--value"], text=True
    ).strip()

def reject(message):
    print("RESET_BLOCKED:", message, file=sys.stderr)
    sys.exit(3)

if os.geteuid() != 0 or os.environ.get("RESET_NATIVE_EXPERIMENTAL_AUTH") != "erase":
    reject("Root and RESET_NATIVE_EXPERIMENTAL_AUTH=erase required")
uid_text = show("User")
if not uid_text or uid_text == "root":
    reject("Native service has no dedicated non-root User; refusing unsafe cleanup")
account = pwd.getpwnam(uid_text)
home = Path(account.pw_dir).resolve()
if str(home) in ("/", "/root"):
    reject("Native service home is unsafe")
# Unit-specific environment variables may carry provider keys that repopulate
# Native after auth.json is deleted. Report names only and refuse partial success.
unit_env = show("Environment")
names = sorted(set(k for k in re.findall(r"(?:^|\s)([A-Za-z_][A-Za-z_0-9]*)=", unit_env) if KEY_RE.match(k)))
files = show("EnvironmentFiles")
for file_path in re.findall(r"(?:^|\s)-?(/[^\s(]+)", files):
    path = Path(file_path)
    if not path.is_file():
        continue
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeError):
        reject("Cannot inspect service environment file (contents never printed)")
    for line in lines:
        match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=", line)
        if match and KEY_RE.match(match.group(1)):
            names.append(match.group(1))
if names:
    reject("Provider credentials still configured in Native service environment: "
           + ", ".join(sorted(set(names))) + ". Remove these from the Native service environment first.")

# Only OpenCode's credential store, never session/project/history/config files.
candidates = [
    home / ".local/share/opencode/auth.json",
    home / ".local/share/opencode/auth.json.bak",
    Path("/var/lib/opencode-native-test/.local/share/opencode/auth.json"),
]
xdg_data = os.environ.get("XDG_DATA_HOME", "")
if xdg_data:
    base = Path(xdg_data).resolve()
    if base.is_relative_to(home) or base.is_relative_to(Path("/var/lib/opencode-native-test")):
        candidates.append(base / "opencode/auth.json")
paths = sorted(set(p.resolve() for p in candidates))
for path in paths:
    if not path.is_file():
        continue
    if not (path.is_relative_to(home) or path.is_relative_to(Path("/var/lib/opencode-native-test"))):
        reject("Credential file outside authorized Native service directories")
    path.unlink()
    print("DELETED_NATIVE_AUTH_FILE", path)
subprocess.check_call(["systemctl", "restart", SERVICE])
subprocess.check_call(["systemctl", "is-active", "--quiet", SERVICE])
print("NATIVE_AUTH_RESET_DONE; no Gateway database, activation or billing changes")
print("Browser localStorage connection hints must be cleared on each test browser separately.")
