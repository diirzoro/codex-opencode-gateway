#!/usr/bin/env python3
"""Reset experimental OpenCode Native provider credentials (not Gateway billing).

Read service-process environment and the Native service user's actual data
directories. Never display token values or delete projects/sessions/database.
The operation fails if it cannot prove that non-built-in connections are gone.
"""
import json
import os
import pwd
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SERVICE = "opencode-native-test.service"
PROVIDER_TOKEN = re.compile(
    r"(?:API[_-]?KEY|ACCESS[_-]?TOKEN|AUTH[_-]?TOKEN|CLIENT[_-]?SECRET|"
    r"CREDENTIAL|SECRET[_-]?KEY|API[_-]?TOKEN|AUTHORIZATION)$", re.I
)
PROVIDER_PREFIX = re.compile(
    r"(OPENAI|ANTHROPIC|DEEPSEEK|OPENROUTER|GEMINI|GOOGLE|MISTRAL|"
    r"COHERE|GROQ|TOGETHER|FIREWORKS|CEREBRAS|XAI|ZAI|MOONSHOT|KIMI|"
    r"PERPLEXITY|DASHSCOPE|SILICONFLOW|VOLCENGINE|MINIMAX|GLM|"
    r"DEEPINFRA|REPLICATE|AZURE|BEDROCK|VERTEX|OPENCODE|OLLAMA|"
    r"ANYSPHERE|CLAUDE|QWEN|NOVITA)", re.I
)

def fail(msg):
    print("NATIVE_AUTH_RESET_BLOCKED:", msg, file=sys.stderr)
    raise SystemExit(3)

def show(prop):
    return subprocess.check_output(
        ["systemctl", "show", SERVICE, "-p", prop, "--value"], text=True
    ).strip()

def env_map(binary):
    result = {}
    for part in binary.split(b"\0"):
        if b"=" not in part:
            continue
        k, v = part.split(b"=", 1)
        result[k.decode("utf-8", "replace")] = v.decode("utf-8", "replace")
    return result

def credential_name(name):
    return bool(PROVIDER_TOKEN.search(name) and PROVIDER_PREFIX.search(name))

if os.geteuid() or os.getenv("RESET_NATIVE_EXPERIMENTAL_AUTH") != "erase":
    fail("Root and RESET_NATIVE_EXPERIMENTAL_AUTH=erase required")
name = show("User")
if not name or name == "root":
    fail("Native service must use an existing dedicated non-root User")
user = pwd.getpwnam(name)
home = Path(user.pw_dir).resolve()
pid = int(show("MainPID") or 0)
if pid <= 0:
    fail("Native service has no active MainPID; cannot inspect runtime environment")
try:
    proc_env = env_map(Path(f"/proc/{pid}/environ").read_bytes())
except OSError:
    fail("Cannot inspect service process environment")
unit_env = show("Environment")
keys = set(k for k in re.findall(r"(?:^|\s)([A-Za-z_][A-Za-z_0-9]*)=", unit_env)
           if credential_name(k))
keys.update(k for k in proc_env if credential_name(k))
# EnvironmentFiles can inject persistent keys independently of auth.json.
for entry in re.findall(r"(?:^|\s)-?(/[^\s(]+)", show("EnvironmentFiles")):
    p = Path(entry)
    if not p.is_file():
        continue
    try:
        for line in p.read_text().splitlines():
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=", line)
            if m and credential_name(m.group(1)):
                keys.add(m.group(1))
    except (OSError, UnicodeError):
        fail("Cannot inspect service EnvironmentFile")
if keys:
    fail("Native environment still sets provider credentials (variable names only): "
         + ", ".join(sorted(keys)) + ". Remove from its service configuration first.")

roots = [home, Path("/var/lib/opencode-native-test")]
for key in ("HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME"):
    value = proc_env.get(key)
    if value and value.startswith("/"):
        roots.append(Path(value))
# Do not traverse the Gateway installation or any arbitrary environment paths.
approved = [home.resolve(), Path("/var/lib/opencode-native-test").resolve()]
paths = set()
for root in roots:
    base = root.resolve()
    if not any(base == a or base.is_relative_to(a) for a in approved):
        continue
    paths.add(base / ".local/share/opencode/auth.json")
    paths.add(base / "opencode/auth.json")
    paths.add(base / "auth.json" if base.name == "opencode" else base / ".config/opencode/auth.json")
    paths.add(base / ".local/share/opencode/auth.json.bak")
    paths.add(base / "opencode/auth.json.bak")
# Examine only OpenCode configuration metadata for possible inline provider
# keys; do not print or delete configuration, policies, or model definitions.
config_paths = set()
for root in roots:
    base = root.resolve()
    if not any(base == a or base.is_relative_to(a) for a in approved):
        continue
    for folder in (base / ".config/opencode", base / "opencode"):
        for fn in ("opencode.json", "opencode.jsonc"):
            config_paths.add(folder / fn)
for config in sorted(config_paths):
    if not config.is_file():
        continue
    try:
        contents = config.read_text()
    except (OSError, UnicodeError):
        fail("Could not inspect Native configuration source")
    # Reject inline credential definitions; removal must be intentional and
    # not destroy the rest of the OpenCode configuration.
    if re.search(r'["\'](?:apiKey|api_key|accessToken|access_token|secret)["\']\s*:', contents, re.I):
        fail("Inline provider credentials detected in Native configuration: " + str(config))

found = [p for p in sorted(paths) if p.is_file()]
print("NATIVE_AUTH_STORE_FILES_FOUND", len(found))
# Stop the service to prevent it rewriting the auth store while deleting.
subprocess.check_call(["systemctl", "stop", SERVICE])
try:
    for p in found:
        resolved = p.resolve()
        if p.is_symlink() or not any(resolved.is_relative_to(a) for a in approved):
            fail("Unsafe credential path, refusing deletion")
        p.unlink()
        print("DELETED_NATIVE_AUTH_FILE", str(p))
finally:
    subprocess.check_call(["systemctl", "start", SERVICE])
subprocess.check_call(["systemctl", "is-active", "--quiet", SERVICE])
# The provider endpoint is Native's runtime observation, not the browser's
# cached connection state. Fail rather than report a false successful cleanup.
connected = None
for attempt in range(12):
    try:
        with urllib.request.urlopen("http://127.0.0.1:18097/provider", timeout=8) as response:
            result = json.load(response)
        if isinstance(result, dict) and isinstance(result.get("connected"), list):
            connected = result["connected"]
            break
    except (OSError, ValueError, TimeoutError):
        time.sleep(2)
if connected is None:
    fail("Native restarted, but provider inventory could not be verified")
remaining = sorted(str(v) for v in connected if str(v) != "opencode")
if remaining:
    fail("Native still reports connected provider IDs: " + ", ".join(remaining)
         + ". Check Native config/environment and running service identity.")
print("NATIVE_AUTH_RESET_VERIFIED", "providers=opencode-only-or-none",
      "deleted_files=" + str(len(found)))
print("GATEWAY_DATABASE_BILLING_ACTIVATION_UNCHANGED")
