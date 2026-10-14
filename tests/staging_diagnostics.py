"""Opt-in tracing. Never record SQL values, URL queries or auth bodies."""
import contextvars
import itertools
import json
import re
import threading
import time
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

_scope = contextvars.ContextVar("audit_request", default="background")
_sequence = itertools.count(1)
_write_lock = threading.Lock()


def install(app, trace_path):
    from sqlalchemy import event
    from backend.app.database import engine
    from backend.app.services import opencode
    destination = Path(trace_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    def emit(kind, **fields):
        record = dict(t=round(time.monotonic(), 6), request=_scope.get(), event=kind, **fields)
        with _write_lock, destination.open("a") as output:
            output.write(json.dumps(record)+"\n")

    @event.listens_for(engine, "before_cursor_execute")
    def query_begin(conn, cursor, statement, parameters, context, executemany):
        context.audit_started = time.monotonic()
        # Table names only; never log the statement or bind parameters.
        match = re.search(r"\b(?:FROM|INTO|UPDATE)\s+([a-z_][a-z_0-9]*)", statement, re.I)
        emit("sql.begin", connection=id(conn), operation=statement.split()[0].upper(),
             table=match.group(1) if match else "metadata")

    @event.listens_for(engine, "after_cursor_execute")
    def query_end(conn, cursor, statement, parameters, context, executemany):
        emit("sql.end", connection=id(conn), ms=round((time.monotonic()-context.audit_started)*1000, 2))

    for action in ("begin", "commit", "rollback"):
        def transaction(conn, action=action):
            emit("transaction."+action, connection=id(conn))
        event.listen(engine, action, transaction)

    def instrument(target, name):
        original = getattr(target, name)
        @wraps(original)
        def measured(*args, **kwargs):
            started = time.monotonic()
            fields = {}
            if name == "request" and len(args) >= 3:
                fields = {"method": args[1], "path": urlsplit(args[2]).path}
            emit("runtime."+name+".begin", **fields)
            try:
                result = original(*args, **kwargs)
            except Exception as error:
                emit("runtime."+name+".error", error=type(error).__name__)
                raise
            else:
                emit("runtime."+name+".end", ms=round((time.monotonic()-started)*1000, 2))
                return result
        setattr(target, name, measured)

    for name in ("for_account", "for_workspace", "_initialize"):
        instrument(opencode, name)
    instrument(opencode.OpenCodeService, "request")
    instrument(opencode.OpenCodeService, "health")

    class TraceApp:
        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                return await app(scope, receive, send)
            identifier = "request-"+str(next(_sequence))
            token = _scope.set(identifier)
            started = time.monotonic()
            path = re.sub(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", ":id", scope["path"])
            emit("http.begin", method=scope["method"], path=path)
            async def observed_send(message):
                if message["type"] == "http.response.start":
                    emit("http.response", status=message["status"], ms=round((time.monotonic()-started)*1000, 2))
                await send(message)
            try:
                await app(scope, receive, observed_send)
            finally:
                emit("http.end", ms=round((time.monotonic()-started)*1000, 2))
                _scope.reset(token)
    return TraceApp()
