"""Project-independent, read-only OpenCode catalog discovery.

Never use workspace credentials or return the shared OpenCode daemon's
connection state. Provider policy must be applied by the requesting route.
"""
import threading
import time
from copy import deepcopy

from fastapi import HTTPException

from ..config import settings
from .opencode import OpenCodeService


_catalog_lock = threading.Lock()
_catalog_cache = {}
CATALOG_TTL_SECONDS = 30.0


def public_catalog(path, *, agents=False, service=None):
    """Read one native OpenCode catalog with a bounded loopback HTTP client."""
    if path not in {"/provider", "/agent"}:
        raise ValueError("Unsupported public catalog path")
    if agents != (path == "/agent"):
        raise ValueError("Catalog type must match the requested OpenCode endpoint")
    # Cache locking must not serialize slow native HTTP across different users.
    key = (path, service.generation if service is not None else None,
           getattr(service, 'discovery_revision', 0) if service is not None else 0)
    with _catalog_lock:
        now = time.monotonic()
        for stale in [k for k,v in _catalog_cache.items() if now-v[0] >= CATALOG_TTL_SECONDS]:
            _catalog_cache.pop(stale,None)
        cached = _catalog_cache.get(key)
        if cached:
            return deepcopy(cached[1])
    own_service = service is None
    if own_service:
        service = OpenCodeService(settings.opencode_url)
    try:
        core = 'agents' if agents else 'provider_data'
        data = (service._core_value(core,path) if hasattr(service,'_core_value') else service.request('GET',path))
        if agents:
            if not isinstance(data,list):
                raise HTTPException(502,'OpenCode returned an invalid agent catalog')
            public = [{'name':r['name'],'mode':r.get('mode'),'hidden':r.get('hidden',False)}
                      for r in data if isinstance(r,dict) and isinstance(r.get('name'),str) and 0<len(r['name'])<=120]
        else:
            if not isinstance(data,dict) or not isinstance(data.get('all'),list):
                raise HTTPException(502,'OpenCode returned an invalid provider catalog')
            public = {'all':[{'id':r['id'],'name':r.get('name',r['id']),
                              'models':{k:None for k in r.get('models',{})}}
                             for r in data['all'] if isinstance(r,dict) and isinstance(r.get('id'),str)
                             and isinstance(r.get('models',{}),dict)],
                      'connected':[],'gateway_disconnected':[],'default':data.get('default',{})}
        with _catalog_lock:
            if len(_catalog_cache)>=256:
                _catalog_cache.pop(min(_catalog_cache,key=lambda k:_catalog_cache[k][0]))
            _catalog_cache[key]=(time.monotonic(),public)
        return deepcopy(public)
    finally:
        if own_service:service.close()
