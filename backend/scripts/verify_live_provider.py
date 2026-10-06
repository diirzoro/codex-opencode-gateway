"""Live-provider verification: real OpenCode runtime + real provider + real prompt edit.

Run with the operator's own environment (DeepSeek API key in ~/.local/share/opencode/auth.json).
This script uses the actual Gateway service code paths (opencode.for_workspace,
providers.set_api_key, workspaces.files/diff/status) against an isolated temp workspace.
It never prints the credential and never writes it to the repository.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

tmp = Path(tempfile.mkdtemp(prefix="gw-live-"))
os.environ.update(
    TESTING="true",
    DATABASE_URL="sqlite+pysqlite:///" + (tmp / "test.db").as_posix(),
    COOKIE_SECURE="false",
    APP_HOST="127.0.0.1",
    OPENCODE_RUNTIME_MODE="local",
    WORKSPACE_ROOT=str(tmp / "workspaces"),
    RUNTIME_ROOT=str(tmp / "runtime"),
    OPENCODE_BASE_URL="http://127.0.0.1:4096",
)

from app.database import Base, engine, SessionLocal  # noqa: E402
from app.models import Country, Project, User, Workspace  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402
from app.services import opencode, providers, workspaces  # noqa: E402
from datetime import datetime, timezone, timedelta  # noqa: E402

class AllowPolicy:
    require_tool_approval = False
    allowed_providers = "[]"
    allowed_models = "[]"
    allowed_tools = "[]"

results = {}

def main():
    auth_path = Path.home() / ".local/share/opencode/auth.json"
    auth = json.loads(auth_path.read_text())
    entry = auth.get("deepseek") or {}
    key = entry.get("key")
    if not key:
        print("RESULT: no deepseek api key found")
        return
    provider = "deepseek"
    auth_method = entry.get("type", "api")

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.get(Country, 1):
            db.add(Country(id=1, name="Yemen", code="YE", enabled=True))
        user = User(id=uuid.uuid4(), username="livetest", email="livetest@example.com",
                    password_hash=hash_password("NotUsed123!"), phone="+967000000",
                    postal_code="00000", country_id=1, role="customer", status="active",
                    preferred_language="en", preferred_theme="light",
                    trial_started_at=datetime.now(timezone.utc),
                    trial_ends_at=datetime.now(timezone.utc) + timedelta(days=10),
                    last_login_at=datetime.now(timezone.utc))
        db.add(user); db.commit()
        project = Project(id=uuid.uuid4(), user_id=user.id, name="live-provider-check", source_type="blank", default_branch="work")
        workspace = Workspace(id=uuid.uuid4(), project_id=project.id, user_id=user.id, status="ready")
        db.add(project); db.add(workspace); db.commit()
        repo = workspaces.root_for(workspace)
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "README.md").write_text("# live-provider-check\n", encoding="utf-8")
        workspaces.git(workspace, "init", "--initial-branch=work")
        workspaces.git(workspace, "add", "--all")
        workspaces.git(workspace, "commit", "-m", "init", check=False)

        opencode.configure_policy(AllowPolicy())
        service = opencode.for_workspace(workspace)
        health = service.health()
        results["version"] = health.get("version")

        # 1) Connect the provider through the secure (server-side) flow.
        assert providers.set_api_key(service, provider, key) is True
        connected = providers.is_connected(service, provider)
        results["connected"] = connected
        assert connected

        # Discover the model id from the real runtime capability list.
        prov_data = service.request("GET", "/provider")
        deepseek = next((p for p in prov_data.get("all", []) if p["id"] == provider), {})
        model_ids = list((deepseek.get("models") or {}).keys())
        model = model_ids[0] if model_ids else "deepseek-chat"
        results["model"] = model

        # 2) Run a real prompt against the isolated workspace. For this autonomous edit,
        #    tools are allowed; the Gateway still enforces ask-by-default for normal sessions.
        session = service.request("POST", "/session", {
            "title": "live-provider-check",
            "permission": [
                {"permission": "*", "pattern": "*", "action": "allow"},
                {"permission": "external_directory", "pattern": "*", "action": "deny"},
            ],
        })
        session_id = session["id"]
        prompt = "Create a file named phase2_verify.txt whose only content is the single line: hello phase2"
        response = service.request("POST", service.session_path(session_id, "/message"),
                                   {"parts": [{"type": "text", "text": prompt}],
                                    "model": {"providerID": provider, "modelID": model}}, 300)
        results["message_returned"] = isinstance(response, dict) and response.get("parts") is not None

        # 3) Prove the prompt edited a real workspace file.
        target = repo / "phase2_verify.txt"
        results["file_created"] = target.exists()
        content = target.read_text(encoding="utf-8") if target.exists() else ""
        results["file_content_ok"] = "hello phase2" in content

        # 4/5) Confirm the edit appears in Gateway Files and Diff.
        listing = workspaces.files(workspace)
        results["files_lists_file"] = any(f["name"] == "phase2_verify.txt" for f in listing)
        diff = workspaces.diff(workspace)["diff"]
        results["diff_shows_edit"] = "phase2_verify.txt" in diff and "hello phase2" in diff

        # 6) Confirm the real assistant/runtime result appears in chat (message text).
        msgs = service.request("GET", service.session_path(session_id, "/message"))
        text = "\n".join(p.get("text", "") for p in (msgs[-1].get("parts", []) if msgs else []) if p.get("type") == "text")
        results["chat_has_result"] = bool(text.strip())

        # 7) Stop during an active generation and verify real cancellation.
        stop_result = {}
        def run_long():
            try:
                service.request("POST", service.session_path(session_id, "/message"),
                                {"parts": [{"type": "text", "text": "Count from 1 to 10000, one number per line."}],
                                 "model": {"providerID": provider, "modelID": model}}, 600)
            except Exception as exc:
                stop_result["stopped"] = True
        t = threading.Thread(target=run_long); t.start()
        time.sleep(3)
        aborted = service.request("POST", service.session_path(session_id, "/abort"))
        results["abort_ack"] = isinstance(aborted, bool) and aborted
        t.join(timeout=20)
        results["stop_terminated"] = stop_result.get("stopped", False) or not t.is_alive()

        # 8) Verify credentials do not appear in files, diff, chat, logs or git status.
        git_status = workspaces.status(workspace)
        leaked_in = []
        for label, value in [("file", content), ("diff", diff), ("chat", text), ("git_status", json.dumps(git_status))]:
            if key and key in value:
                leaked_in.append(label)
        results["secret_leaked_in"] = leaked_in

        opencode.stop_workspace(workspace)

        # 8b) Additional secret scan: runtime log and the Gateway's redaction regex.
        from app.config import settings
        from app.routes.agent import _SECRET_RE
        log_path = Path(settings.runtime_root) / str(user.id) / str(workspace.id) / "runtime.log"
        results["secret_in_log"] = bool(key in log_path.read_text(encoding="utf-8", errors="replace")) if log_path.exists() else False
        results["secret_matches_redaction_regex"] = bool(_SECRET_RE.search("prefix " + key))

    print("RESULT_JSON " + json.dumps(results))
    shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
