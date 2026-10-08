from pathlib import Path
from functools import lru_cache
import hashlib
import re
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from urllib.parse import urlsplit
from .routes import admin, auth, locations, profile
from .routes import workspaces, agent, github, dashboard, plans, billing, management
app = FastAPI(title="OpenCode Gateway API", version="0.1.0")
app.include_router(auth.router); app.include_router(profile.router); app.include_router(locations.router); app.include_router(admin.router)
app.include_router(workspaces.router)
app.include_router(agent.router)
app.include_router(github.router)
app.include_router(dashboard.router)
app.include_router(plans.router)
app.include_router(billing.router)
app.include_router(management.router)
@app.get("/api/health")
def health(): return {"status": "ok"}
frontend = Path(__file__).resolve().parents[2]

# Server-to-server callbacks that are authenticated by signature, not cookies.
_CROSS_SITE_EXEMPT = {"/api/github/webhook"}

@app.middleware("http")
async def browser_boundary(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path not in _CROSS_SITE_EXEMPT:
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site request denied"}, status_code=403)
        if origin and (urlsplit(origin).scheme, urlsplit(origin).netloc) != (request.url.scheme, request.url.netloc):
            return JSONResponse({"detail": "Cross-site request denied"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/") or request.url.path == "/config.js":
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path in {"/", "/index.html"}:
        response.headers["Cache-Control"] = "no-cache"
    elif request.url.path.lstrip("/") in _VERSIONED_ASSETS:
        name = request.url.path.lstrip("/")
        response.headers["Cache-Control"] = ("public, max-age=31536000, immutable"
            if request.query_params.get("v") == asset_version(name) else "public, max-age=0, must-revalidate")
    return response

# Explicit public assets only. Never mount the repository, docs or runtime root.
_VERSIONED_ASSETS = {"app.js", "enhancements.js", "management.js", "dashboards.js", "runtime-client.js", "styles.css"}

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

for url, name in {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/enhancements.js": "enhancements.js", "/management.js": "management.js", "/dashboards.js": "dashboards.js", "/runtime-client.js": "runtime-client.js", "/styles.css": "styles.css", "/config.js": "config.js", "/assets/yemen-hero.svg": "assets/yemen-hero.svg"}.items():
    app.add_api_route(url, public_file(name), methods=["GET"], include_in_schema=False)
