"""Fixed executable preview launch profiles shared by Gateway and Worker.

Keep this module dependency-free: the dedicated Preview Worker must be able to
prepare snapshots without importing FastAPI, SQLAlchemy or Gateway settings.
Untrusted users never choose arbitrary commands, images, ports or mounts.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class LaunchProfile:
    family: str
    argv: tuple[str, ...]
    internal_port: int = 8080


PROFILES = {
    "nextjs": LaunchProfile("node", ("./node_modules/.bin/next", "dev",
                                      "--hostname", "0.0.0.0", "--port", "8080")),
    "vite": LaunchProfile("node", ("./node_modules/.bin/vite", "--host",
                                    "0.0.0.0", "--port", "8080", "--strictPort")),
    "angular": LaunchProfile("node", ("./node_modules/.bin/ng", "serve",
                                      "--host", "0.0.0.0", "--port", "8080")),
    "nuxt": LaunchProfile("node", ("./node_modules/.bin/nuxt", "dev",
                                   "--host", "0.0.0.0", "--port", "8080")),
    "django": LaunchProfile("python", ("python", "manage.py", "runserver",
                                        "0.0.0.0:8080", "--noreload")),
    "laravel": LaunchProfile("php", ("php", "artisan", "serve",
                                    "--host=0.0.0.0", "--port=8080")),
}
