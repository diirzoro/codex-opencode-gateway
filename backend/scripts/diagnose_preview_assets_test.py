#!/usr/bin/env python3
"""Read-only GET checks inside an already running TEST Preview container.

No prepare/start/stop, configuration edits, shell app execution or customer
content output. Run as root on TEST; UUID must be the owner's QA workspace.
"""
import argparse
import base64
import json
from pathlib import Path
import urllib.error
import urllib.request
import uuid

ENDPOINT = 'http://127.0.0.1:8791/v1/'
PATHS = ('/', '/style.css', '/app.js', '/nested/page')
TYPES = {'text/html', 'text/css', 'text/javascript', 'application/javascript',
         'application/json', 'text/plain', 'application/octet-stream'}
ERRORS = {'unauthorized', 'unregistered_job', 'not_running', 'application_not_ready',
          'worker_operation_failed', 'worker_internal_error'}


def request(operation, job_id, token, path=None):
    payload = {'job_id': job_id}
    if path is not None:
        payload['path'] = path
    req = urllib.request.Request(ENDPOINT + operation,
        data=json.dumps(payload).encode(), method='POST',
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read(524289)
        if len(raw) > 524288:
            raise ValueError('oversized response')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError('invalid response')
        return result


def probe(job_id, token):
    # Canonical UUID prevents arbitrary jobs or path selection via CLI arguments.
    job_id = str(uuid.UUID(job_id))
    if len(token) < 32:
        raise ValueError('invalid token')
    state = request('status', job_id, token).get('state')
    print(json.dumps({'probe': 'worker_state', 'state': state if state in
        {'ready', 'running', 'stopped', 'failed'} else 'unknown'}))
    if state != 'running':
        print('BLOCKED: QA Preview is not running; no start was attempted.')
        return 1
    failed = False
    for path in PATHS:
        try:
            data = request('fetch', job_id, token, path)
            status = data.get('status')
            if type(status) is not int or not 200 <= status <= 599:
                raise ValueError('invalid status')
            body = base64.b64decode(data['body'], validate=True)
            if len(body) > 262144:
                raise ValueError('oversized body')
            mime = str(data.get('type', '')).split(';')[0].strip().lower()
            print(json.dumps({'probe': 'worker_asset', 'path': path, 'status': status,
                'type': mime if mime in TYPES else 'other', 'bytes': len(body)}))
            failed = failed or status != 200
        except urllib.error.HTTPError as error:
            # Response text may contain customer details; never echo it.
            try:
                code = json.loads(error.read(1024)).get('error')
            except (ValueError, AttributeError):
                code = None
            print(json.dumps({'probe': 'worker_asset', 'path': path,
                'worker_status': error.code, 'error': code if code in ERRORS else 'unclassified'}))
            failed = True
    print('Scope: container GET responses only; browser cookies/framing and JavaScript execution are not certified.')
    return int(failed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace_id', type=lambda value: str(uuid.UUID(value)))
    args = parser.parse_args()
    try:
        config = {}
        for line in Path('/etc/opencode-preview-worker-test.env').read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip().strip('"').strip("'")
        return probe(args.workspace_id, config.get('PREVIEW_WORKER_TOKEN', ''))
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Includes urllib errors; do not expose their body, URL or exception value.
        print('BLOCKED: TEST Preview read-only probe unavailable (' + type(error).__name__ + ').')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
