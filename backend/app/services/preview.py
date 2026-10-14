"""Read-only HTML preview; never starts a shell or executes a project on the host."""
import base64
import html
import mimetypes
import posixpath
from html.parser import HTMLParser
from pathlib import PurePosixPath
from fastapi import HTTPException
from . import workspaces


class StaticPreview(HTMLParser):
    def __init__(self, workspace, filename):
        super().__init__(convert_charrefs=False)
        self.workspace=workspace
        self.parent=str(PurePosixPath(filename).parent)
        self.parts=[]
        self.skip_script=False
        self.bytes=0

    def local(self, value):
        if not value or ':' in value or value.startswith('//') or value.startswith('#'):
            return None
        name=posixpath.normpath(value.lstrip('/') if value.startswith('/') else posixpath.join(self.parent,value.split('?',1)[0]))
        path=workspaces.safe_path(self.workspace,name)
        if not path.is_file() or path.stat().st_size>1000000:return None
        self.bytes+=path.stat().st_size
        if self.bytes>5000000:raise HTTPException(413,'Preview assets exceed 5 MB')
        return path

    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='base':return
        if tag=='link' and values.get('rel')=='stylesheet':
            path=self.local(values.get('href'))
            if path:
                self.parts.append('<style>'+path.read_text(encoding='utf-8').replace('</style','<\\/style')+'</style>');return
        if tag=='script' and values.get('src'):
            path=self.local(values['src'])
            if path:
                self.parts.append('<script>'+path.read_text(encoding='utf-8').replace('</script','<\\/script')+'</script>')
            self.skip_script=True;return
        if tag=='img' and values.get('src'):
            path=self.local(values['src'])
            if path:
                values['src']='data:'+(mimetypes.guess_type(path.name)[0] or 'application/octet-stream')+';base64,'+base64.b64encode(path.read_bytes()).decode()
        self.parts.append('<'+tag+''.join(' '+name+('="'+html.escape(value,quote=True)+'"' if value is not None else '') for name,value in values.items())+'>')

    def handle_endtag(self,tag):
        if tag=='script' and self.skip_script:self.skip_script=False;return
        self.parts.append('</'+tag+'>')

    def handle_data(self,data):
        if not self.skip_script:self.parts.append(data)
    def handle_entityref(self,name):self.parts.append('&'+name+';')
    def handle_charref(self,name):self.parts.append('&#'+name+';')
    def handle_comment(self,data):self.parts.append('<!--'+data+'-->')
    def handle_decl(self,decl):self.parts.append('<!'+decl+'>')


def render(workspace,path='index.html'):
    if not path.lower().endswith(('.html','.htm')):
        raise HTTPException(422,'Static preview requires an HTML entry file')
    parser=StaticPreview(workspace,path)
    parser.feed(workspaces.content(workspace,path))
    policy="default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; form-action 'none'; base-uri 'none'"
    return {"mode":"static","path":path,"html":'<meta http-equiv="Content-Security-Policy" content="'+policy+'">'+''.join(parser.parts),
            "browser_automation":False,"limitations":"Read-only sandboxed HTML preview. Backend servers and browser automation are not configured."}


# Project preview detection is intentionally read-only. Starting arbitrary
# uploaded code on the gateway host is forbidden; a containerized runner is
# required before any dynamically served preview can be enabled.
def detect(workspace):
    """Describe the actual project, not assume index.html exists.

    Detection reads only small, user-owned manifest files through safe_path.
    It never runs package install scripts, build hooks, shell commands or apps.
    """
    import json
    candidates = (
        ("package.json", "node"), ("pyproject.toml", "python"),
        ("requirements.txt", "python"), ("manage.py", "django"),
        ("artisan", "laravel"), ("composer.json", "php"),
        ("Cargo.toml", "rust"), ("go.mod", "go"), ("pubspec.yaml", "flutter"),
        ("pom.xml", "java"), ("build.gradle", "java"),
        ("index.html", "html"),
    )
    found = []
    manifest = {}
    for filename, kind in candidates:
        target = workspaces.safe_path(workspace, filename)
        if not target.is_file() or target.is_symlink() or target.stat().st_size > 250_000:
            continue
        found.append(filename)
        if filename == "package.json":
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    dependencies = {**(data.get("dependencies") or {}),
                                    **(data.get("devDependencies") or {})}
                    if not isinstance(dependencies,dict): dependencies={}
                    scripts = data.get("scripts") or {}
                    manifest = {"dependencies":list(dependencies)[:120],
                                "scripts":list(scripts)[:40] if isinstance(scripts,dict) else []}
            except (ValueError,UnicodeError,TypeError):
                manifest = {}
    files = set(found)
    if "package.json" in files:
        deps = set(manifest.get("dependencies",[]))
        if "next" in deps: kind = "nextjs"
        elif "vite" in deps: kind = "vite"
        elif "@angular/core" in deps: kind = "angular"
        elif "nuxt" in deps: kind = "nuxt"
        elif "svelte" in deps or "@sveltejs/kit" in deps: kind = "svelte"
        elif "react" in deps: kind = "react"
        elif "vue" in deps: kind = "vue"
        else: kind = "node"
    elif "manage.py" in files: kind = "django"
    elif "artisan" in files: kind = "laravel"
    elif "pyproject.toml" in files or "requirements.txt" in files: kind = "python"
    elif "composer.json" in files: kind = "php"
    elif "Cargo.toml" in files: kind = "rust"
    elif "go.mod" in files: kind = "go"
    elif "pubspec.yaml" in files: kind = "flutter"
    elif "pom.xml" in files or "build.gradle" in files: kind = "java"
    elif "index.html" in files: kind = "html"
    else: kind = "unknown"
    return {
        "framework": kind,
        "manifest_files": found,
        "preview_mode": "static" if kind == "html" else "requires_isolated_runner",
        "runnable_preview_available": kind == "html",
        "supported_by_detection": kind != "unknown",
        "message": "Dynamic project previews need a secure isolated runner; no project code was executed."
                   if kind != "html" else "Static HTML preview available.",
    }
