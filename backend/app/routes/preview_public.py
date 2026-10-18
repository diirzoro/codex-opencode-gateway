"""Cookie-independent, read-only browser relay on the dedicated Preview origin."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..services import preview_access, preview_runner

router = APIRouter(tags=['preview-browser'])


@router.api_route('/preview/{ticket}/{asset_path:path}', methods=['GET', 'HEAD'])
def browser_asset(ticket: str, asset_path: str, request: Request, db: Session = Depends(get_db)):
    workspace, gateway, lease = preview_access.authorize(ticket, request, db)
    path = '/' + asset_path
    if request.url.query:
        path += '?' + request.url.query
    response = preview_runner.fetch_asset(workspace, path, relay_prefix='/preview/' + ticket + '/', browser_lease=lease)
    # The opaque sandbox also applies on direct navigation. Modules/fetch can
    # read only the bearer-scoped Preview GET result; no credentialed CORS.
    response.headers['Content-Security-Policy'] = "sandbox allow-scripts; frame-ancestors " + gateway
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
    request.state.public_preview_response = True
    if request.method == 'HEAD':
        response.body = b''
    return response
