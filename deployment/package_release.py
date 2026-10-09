"""Build a source-only ZIP for manual upload; never contacts a server."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT.parent / "opencode-gateway-release.zip"
EXAMPLE_ENV_FILES = {".env.example", "deployment/.env.production.example"}
EXCLUDED_DIRS = {
    ".git", ".audit", ".venv", ".venv-local", "venv", "node_modules",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "playwright-report", "test-results", "tests", "test", "testing",
    "runtime", "workspaces", "reference",
}
EXCLUDED_FILES = {
    ".env", ".env.local", ".env.production", ".env.paypal.local",
    "playwright.config.cjs", "RELEASE_MANIFEST.txt",
}
EXCLUDED_SUFFIXES = {
    ".pyc", ".pyo", ".log", ".db", ".sqlite", ".sqlite3", ".pem",
    ".key", ".p12", ".pfx", ".bak", ".dump",
}
REQUIRED_RELEASE_FILES = {
    "README.md",
    "PROJECT_MEMORY.md",
    "PROJECT_ISSUES_AND_IMPROVEMENT_PLAN.md",
    "backend/app/services/opencode.py",
    "backend/alembic/versions/0012_advanced_trial.py",
    "backend/alembic/versions/0013_login_identity.py",
    "deployment/opencode-gateway.service",
    "deployment/.env.production.example",
    "deployment/OPENCODE_INTEGRATION.md",
    "deployment/GITHUB_INTEGRATION.md",
    "deployment/NETWORK_CONFIGURATION.md",
    "deployment/check_opencode_runtime.sh",
}


def allowed(relative: Path) -> bool:
    parts = relative.parts
    name = relative.name
    posix = relative.as_posix()
    if any(part in EXCLUDED_DIRS for part in parts[:-1]):
        return False
    if name in EXCLUDED_FILES or (name.startswith(".env") and posix not in EXAMPLE_ENV_FILES):
        return False
    if Path(name).suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if name.endswith((".test.js", ".spec.js", ".test.ts", ".spec.ts", ".test.py", ".spec.py")):
        return False
    return True


def main() -> None:
    output = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else DEFAULT_OUTPUT.resolve()
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python deployment/package_release.py [output.zip]")
    try:
        output.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise SystemExit("Choose an output path outside the project directory")
    if output.suffix.lower() != ".zip":
        raise SystemExit("Output must be a .zip file")
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing package: {output}")

    files: list[Path] = []
    for current, directories, filenames in os.walk(ROOT, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRS)
        for filename in filenames:
            path = current_path / filename
            if path.is_symlink():
                continue
            relative = path.relative_to(ROOT)
            if allowed(relative):
                files.append(path)
    files.sort(key=lambda path: path.relative_to(ROOT).as_posix().casefold())
    if not files:
        raise SystemExit("No source files found; no package created")
    included = {path.relative_to(ROOT).as_posix() for path in files}
    missing = sorted(REQUIRED_RELEASE_FILES - included)
    if missing:
        raise SystemExit("Required release files are missing: " + ", ".join(missing))

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = [
        "OpenCode Gateway source release",
        "Generated locally for manual review and upload. No server was contacted.",
        "Excluded: secrets, local environment files, databases, runtime/workspace data, dependencies, tests, and audit artifacts.",
        f"Included source files: {len(files)}",
        "",
    ]
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
            for path in files:
                relative = path.relative_to(ROOT).as_posix()
                archive.write(path, f"project/{relative}")
                manifest.append(relative)
            archive.writestr("project/RELEASE_MANIFEST.txt", "\n".join(manifest) + "\n")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        missing = {f"project/{name}" for name in REQUIRED_RELEASE_FILES} - names
        forbidden = []
        for name in names:
            if not name.startswith("project/"):
                forbidden.append(name)
                continue
            relative = Path(*Path(name).parts[1:])
            if name != "project/RELEASE_MANIFEST.txt" and not allowed(relative):
                forbidden.append(name)
        if missing or forbidden:
            output.unlink(missing_ok=True)
            raise SystemExit(f"Release archive verification failed; missing={sorted(missing)}, forbidden={sorted(forbidden)}")
    print(f"Created {output}")
    print(f"Included {len(files)} source files; see project/RELEASE_MANIFEST.txt inside the archive.")


if __name__ == "__main__":
    main()