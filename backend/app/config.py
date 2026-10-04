from dataclasses import dataclass
import os
import re
from pathlib import Path
from urllib.parse import urlparse

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}

def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value

def parse_bool(name: str, default: str) -> bool:
    value = os.getenv(name, default).strip().lower()
    if value in _TRUE: return True
    if value in _FALSE: return False
    raise RuntimeError(f"{name} must be true or false")

def parse_int(name: str, default: str, minimum: int, maximum: int) -> int:
    try: value = int(os.getenv(name, default))
    except ValueError as exc: raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value

def optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None

@dataclass(frozen=True)
class Settings:
    database_url: str
    session_cookie_name: str
    session_days: int
    cookie_secure: bool
    app_host: str
    app_port: int
    testing: bool
    workspace_root: Path
    runtime_root: Path
    runtime_mode: str
    opencode_binary: str
    opencode_url: str
    public_base_url: str
    github_app_id: int | None
    github_app_slug: str | None
    github_client_id: str | None
    github_client_secret: str | None
    github_private_key: str | None
    github_webhook_secret: str | None
    github_callback_url: str
    github_api_base: str
    github_web_base: str
    credentials_encryption_key: str | None

    @property
    def github_configured(self) -> bool:
        return bool(self.github_app_id and self.github_app_slug and self.github_private_key)

    @classmethod
    def from_environment(cls):
        testing = parse_bool("TESTING", "false")
        database_url = required("DATABASE_URL")
        allowed = ("postgresql://", "postgresql+psycopg://")
        if not database_url.startswith(allowed) and not (testing and database_url.startswith("sqlite")):
            raise RuntimeError("DATABASE_URL must use PostgreSQL with psycopg")
        cookie = os.getenv("SESSION_COOKIE_NAME", "gateway_session").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cookie):
            raise RuntimeError("SESSION_COOKIE_NAME contains invalid characters")
        host = os.getenv("APP_HOST", "127.0.0.1").strip()
        if host not in {"127.0.0.1", "0.0.0.0", "::1"}:
            raise RuntimeError("APP_HOST must be a valid local bind address")
        mode = os.getenv("OPENCODE_RUNTIME_MODE", "disabled")
        if mode not in {"disabled", "local"}:
            raise RuntimeError("OPENCODE_RUNTIME_MODE must be disabled or local")
        if mode == "local" and host not in {"127.0.0.1", "::1"}:
            raise RuntimeError("Local runtime mode requires a loopback Gateway bind")
        app_port = parse_int("APP_PORT", "8180", 1, 65535)
        base = Path(__file__).resolve().parents[2]
        workspace_root = Path(os.getenv("WORKSPACE_ROOT", str(base / "workspaces"))).resolve()
        runtime_root = Path(os.getenv("RUNTIME_ROOT", str(base / "runtime"))).resolve()
        url = os.getenv("OPENCODE_URL", "http://127.0.0.1:4196").rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
            raise RuntimeError("OPENCODE_URL must be an internal loopback HTTP URL without credentials")
        public_base = os.getenv("PUBLIC_BASE_URL", f"http://{host}:{app_port}").rstrip("/")
        callback = os.getenv("GITHUB_CALLBACK_URL", f"{public_base}/api/github/callback").strip()
        private_key = optional("GITHUB_APP_PRIVATE_KEY")
        if not private_key:
            key_path = optional("GITHUB_APP_PRIVATE_KEY_PATH")
            if key_path:
                try:
                    private_key = Path(key_path).read_text(encoding="utf-8")
                except OSError as exc:
                    raise RuntimeError("GITHUB_APP_PRIVATE_KEY_PATH is not readable") from exc
        app_id_raw = optional("GITHUB_APP_ID")
        github_app_id = None
        if app_id_raw is not None:
            try:
                github_app_id = int(app_id_raw)
            except ValueError as exc:
                raise RuntimeError("GITHUB_APP_ID must be an integer") from exc
        callback_host = urlparse(callback).hostname
        if callback_host not in {"127.0.0.1", "localhost", "::1"} and not callback.startswith("https://"):
            raise RuntimeError("GITHUB_CALLBACK_URL must be HTTPS or a loopback HTTP URL")
        return cls(
            database_url, cookie, parse_int("SESSION_DAYS", "14", 1, 90),
            parse_bool("COOKIE_SECURE", "true"), host, app_port, testing,
            workspace_root, runtime_root, mode, os.getenv("OPENCODE_BINARY", "opencode"), url,
            public_base, github_app_id, optional("GITHUB_APP_SLUG"), optional("GITHUB_CLIENT_ID"),
            optional("GITHUB_CLIENT_SECRET"), private_key, optional("GITHUB_WEBHOOK_SECRET"),
            callback, os.getenv("GITHUB_API_BASE", "https://api.github.com").rstrip("/"),
            os.getenv("GITHUB_WEB_BASE", "https://github.com").rstrip("/"),
            optional("CREDENTIALS_ENCRYPTION_KEY"),
        )

settings = Settings.from_environment()
