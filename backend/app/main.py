from pathlib import Path
from functools import lru_cache
import hashlib
import re
import asyncio
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from urllib.parse import urlsplit
from .routes import admin, auth, locations, profile
from .routes import workspaces, agent, github, dashboard, plans, billing, management, homepage
from .services import workspace_cache, customer_lifecycle, preview_access
from .routes import preview_public, native_sessions

async def retention_maintenance():
    # Retention bookkeeping must not delay the HTML shell or authentication.
    for initialize in (workspace_cache.initialize, customer_lifecycle.initialize):
        try:
            await asyncio.to_thread(initialize)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Retention policy initialization could not complete")
    while True:
        await asyncio.sleep(300)
        from .services import email_notifications, github as github_service
        for job in (workspace_cache.sweep, customer_lifecycle.archive_due, email_notifications.sweep,
                    github_service.expire_pending_authorizations):
            try:
                await asyncio.to_thread(job)
            except Exception:
                # Jobs log sanitized IDs/categories; never print operational data.
                import logging
                logging.getLogger(__name__).warning("Retention maintenance pass could not complete")
        if native_sessions.enabled():
            try:
                from .services import native_catalog_maintenance
                await asyncio.to_thread(native_catalog_maintenance.sweep)
            except Exception:
                import logging
                logging.getLogger(__name__).warning('Native catalog maintenance unavailable; existing catalog and conversations preserved')

async def provider_maintenance():
    from .services import account_provider_sync
    while True:
        await asyncio.sleep(5)
        if not native_sessions.enabled():
            await asyncio.to_thread(account_provider_sync.sweep)

@asynccontextmanager
async def lifespan(app):
    cleanup = asyncio.create_task(retention_maintenance())
    provider_sync = None if native_sessions.enabled() else asyncio.create_task(provider_maintenance())
    try:
        yield
    finally:
        cleanup.cancel()
        if provider_sync is not None:provider_sync.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup
        if provider_sync is not None:
            with suppress(asyncio.CancelledError):
                await provider_sync

preview_access.install_access_log_redaction()

app = FastAPI(title="OpenCode Gateway API", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router); app.include_router(profile.router); app.include_router(locations.router); app.include_router(admin.router)
app.include_router(native_sessions.router)
app.include_router(workspaces.router)
app.include_router(preview_public.router)
app.include_router(agent.router)
app.include_router(github.router)
app.include_router(dashboard.router)
app.include_router(plans.router)
app.include_router(billing.router)
app.include_router(management.router)
app.include_router(homepage.router)
@app.get("/api/health")
def health(): return {"status": "ok"}
frontend = Path(__file__).resolve().parents[2]

# Server-to-server callbacks that are authenticated by signature, not cookies.
_CROSS_SITE_EXEMPT = {"/api/github/webhook"}

@app.middleware("http")
async def browser_boundary(request: Request, call_next):
    if preview_access.is_preview_host(request) and (
        request.method not in {'GET','HEAD'} or not request.url.path.startswith('/preview/')):
        return JSONResponse({'detail':'Not found'},status_code=404,
                            headers={'Cache-Control':'no-store','X-Frame-Options':'DENY'})
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path not in _CROSS_SITE_EXEMPT:
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site request denied"}, status_code=403)
        if origin and (urlsplit(origin).scheme, urlsplit(origin).netloc) != (request.url.scheme, request.url.netloc):
            return JSONResponse({"detail": "Cross-site request denied"}, status_code=403)
    upload_db = None
    match = re.fullmatch(r"/api/workspaces/([0-9a-f-]{36})/files/upload", request.url.path)
    if request.method == "POST" and match:
        import uuid
        try:
            identifier = uuid.UUID(match[1])
        except ValueError:
            return JSONResponse({"detail": "Invalid workspace ID"}, status_code=422)
        try:
            upload_db = await asyncio.to_thread(workspace_cache.begin_upload, request, identifier)
        except HTTPException as error:
            return JSONResponse({"detail": error.detail}, status_code=error.status_code)
    try:
        response = await call_next(request)
    except BaseException:
        if upload_db is not None:
            await asyncio.to_thread(workspace_cache.end_upload, upload_db, False)
        raise
    if upload_db is not None:
        await asyncio.to_thread(workspace_cache.end_upload, upload_db, response.status_code < 400)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    # Correlate failed Preview documents/assets without recording URLs, query
    # parameters, cookies, source, user IDs or arbitrary incoming header values.
    if (request.method == "GET" and response.status_code >= 400
        and re.fullmatch(r"/api/workspaces/[0-9a-f-]{36}/preview/live/.*", request.url.path)):
        import logging
        import uuid
        reference = uuid.uuid4().hex[:12]
        site = request.headers.get("sec-fetch-site", "missing")
        dest = request.headers.get("sec-fetch-dest", "missing")
        site = site if site in {"same-origin", "same-site", "cross-site", "none", "missing"} else "other"
        dest = dest if dest in {"iframe", "document", "script", "style", "image", "empty", "missing"} else "other"
        logging.getLogger(__name__).warning(
            "Preview relay failed status=%d site=%s destination=%s reference=%s",
            response.status_code, site, dest, reference)
        response.headers["X-Preview-Reference"] = reference
    owned_preview = (getattr(request.state, "owned_preview_response", False) is True
        and request.method == "GET"
        and re.fullmatch(r"/api/workspaces/[0-9a-f-]{36}/preview/live/.*", request.url.path)
        and response.headers.get("Content-Security-Policy") == "sandbox allow-scripts")
    public_preview = (preview_access.is_preview_host(request)
        and getattr(request.state,'public_preview_response',False) is True
        and request.method in {'GET','HEAD'}
        and request.url.path.startswith('/preview/'))
    if public_preview:
        if 'X-Frame-Options' in response.headers:
            del response.headers['X-Frame-Options']
        if 'Set-Cookie' in response.headers:
            del response.headers['Set-Cookie']
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
    elif owned_preview:
        # Opaque-origin sandbox is retained. Only our own application can frame
        # an owned preview; authentication/errors and every other page deny it.
        if "X-Frame-Options" in response.headers:
            del response.headers["X-Frame-Options"]
        response.headers["Content-Security-Policy"] = "sandbox allow-scripts; frame-ancestors 'self'"
        response.headers["Referrer-Policy"] = "no-referrer"
    else:
        response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path in {"/", "/index.html"}:
        response.headers["Cache-Control"] = "no-cache"
    elif request.url.path.lstrip("/") in _VERSIONED_ASSETS:
        name = request.url.path.lstrip("/")
        response.headers["Cache-Control"] = ("public, max-age=31536000, immutable"
            if request.query_params.get("v") == asset_version(name) else "public, max-age=0, must-revalidate")
    return response

# Explicit public assets only. Never mount the repository, docs or runtime root.
_VERSIONED_ASSETS = {"app.js", "enhancements.js", "management.js", "dashboards.js", "runtime-client.js", "native-session-client.js", "styles.css"}

@lru_cache(maxsize=32)
def _asset_digest(name, modified, size):
    return hashlib.sha256((frontend / name).read_bytes()).hexdigest()[:16]

def asset_version(name):
    stat = (frontend / name).stat()
    return _asset_digest(name, stat.st_mtime_ns, stat.st_size)

def public_file(name):
    def serve(request: Request):
        if name == "index.html":
            html = (frontend / name).read_text(encoding="utf-8")
            if native_sessions.enabled():
                html=html.replace('<script defer src="runtime-client.js', '<script defer src="native-session-client.js?v=native-test"></script>\n  <script defer src="runtime-client.js')
            # Content versions change automatically when any script/style changes.
            html = re.sub(r'(src|href)="([\w.-]+)\?v=[^"]*"',
                          lambda match: f'{match[1]}="{match[2]}?v={asset_version(match[2])}"'
                          if match[2] in _VERSIONED_ASSETS else match[0], html)
            etag = '"' + hashlib.sha256(html.encode()).hexdigest() + '"'
            response = HTMLResponse(html, headers={"ETag": etag})
        else:
            path = frontend / name
            response = FileResponse(path, stat_result=path.stat())
            etag = response.headers["etag"]
        if any(tag.strip().removeprefix("W/") in {etag, "*"}
               for tag in request.headers.get("if-none-match", "").split(",")):
            return Response(status_code=304, headers={"ETag": etag})
        return response
    return serve

for url, name in {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/enhancements.js": "enhancements.js", "/management.js": "management.js", "/dashboards.js": "dashboards.js", "/runtime-client.js": "runtime-client.js", "/native-session-client.js": "native-session-client.js", "/styles.css": "styles.css"}.items():
    app.add_api_route(url, public_file(name), methods=["GET"], include_in_schema=False)
