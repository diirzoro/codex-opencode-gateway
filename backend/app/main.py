from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from urllib.parse import urlsplit
from .routes import admin, auth, locations, profile
from .routes import workspaces, agent
app = FastAPI(title="OpenCode Gateway API", version="0.1.0")
app.include_router(auth.router); app.include_router(profile.router); app.include_router(locations.router); app.include_router(admin.router)
app.include_router(workspaces.router)
app.include_router(agent.router)
@app.get("/api/health")
def health(): return {"status": "ok"}
frontend = Path(__file__).resolve().parents[2]

@app.middleware("http")
async def browser_boundary(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site request denied"}, status_code=403)
        if origin and (urlsplit(origin).scheme, urlsplit(origin).netloc) != (request.url.scheme, request.url.netloc):
            return JSONResponse({"detail": "Cross-site request denied"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

# Explicit public assets only. Never mount the repository, docs or runtime root.
def public_file(name):
    def serve():
        return FileResponse(frontend / name)
    return serve

for url, name in {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css", "/config.js": "config.js", "/assets/yemen-hero.svg": "assets/yemen-hero.svg"}.items():
    app.add_api_route(url, public_file(name), methods=["GET"], include_in_schema=False)
