from dataclasses import dataclass, field
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
    google_client_id: str | None = field(default=None, repr=False)
    google_client_secret: str | None = field(default=None, repr=False)
    paypal_environment: str = 'sandbox'
    paypal_client_id: str | None = field(default=None,repr=False)
    paypal_client_secret: str | None = field(default=None,repr=False)
    paypal_merchant_id: str | None = None
    paypal_sandbox_decline: bool = False

    @property
    def github_configured(self) -> bool:
        return bool(self.github_app_id and self.github_app_slug and self.github_private_key)

    @classmethod
    def from_environment(cls):
        database_url = required("DATABASE_URL")
        allowed = ("postgresql://", "postgresql+psycopg://")
        if not database_url.startswith(allowed):
            raise RuntimeError("DATABASE_URL must use PostgreSQL with psycopg; SQLite/test databases are not supported")
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
        url = os.getenv("OPENCODE_BASE_URL", "http://127.0.0.1:4096").strip().rstrip("/")
        parsed = urlparse(url)
        try:
            valid_port = parsed.port is None or 1 <= parsed.port <= 65535
        except ValueError:
            valid_port = False
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username is not None or parsed.password is not None or parsed.path or parsed.query or parsed.fragment or not valid_port:
            raise RuntimeError("OPENCODE_BASE_URL must be an internal loopback HTTP origin without credentials")
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
        paypal_environment=os.getenv('PAYPAL_ENVIRONMENT','sandbox').strip()
        if paypal_environment not in {'sandbox','live'}:raise RuntimeError('PAYPAL_ENVIRONMENT must be sandbox or live')
        paypal_decline=parse_bool('PAYPAL_SANDBOX_DECLINE','false')
        if paypal_environment=='live' and paypal_decline:raise RuntimeError('PayPal negative testing is only allowed in sandbox')
        if callback_host not in {"127.0.0.1", "localhost", "::1"} and not callback.startswith("https://"):
            raise RuntimeError("GITHUB_CALLBACK_URL must be HTTPS or a loopback HTTP URL")
        return cls(
            database_url, cookie, parse_int("SESSION_DAYS", "14", 1, 90),
            parse_bool("COOKIE_SECURE", "true"), host, app_port,
            workspace_root, runtime_root, mode, os.getenv("OPENCODE_BINARY", "opencode"), url,
            public_base, github_app_id, optional("GITHUB_APP_SLUG"), optional("GITHUB_CLIENT_ID"),
            optional("GITHUB_CLIENT_SECRET"), private_key, optional("GITHUB_WEBHOOK_SECRET"),
            callback, os.getenv("GITHUB_API_BASE", "https://api.github.com").rstrip("/"),
            os.getenv("GITHUB_WEB_BASE", "https://github.com").rstrip("/"),
            optional("CREDENTIALS_ENCRYPTION_KEY"),
            optional('GOOGLE_CLIENT_ID'),optional('GOOGLE_CLIENT_SECRET'),
            paypal_environment,optional('PAYPAL_CLIENT_ID'),optional('PAYPAL_CLIENT_SECRET'),optional('PAYPAL_MERCHANT_ID'),paypal_decline,
        )

settings = Settings.from_environment()
