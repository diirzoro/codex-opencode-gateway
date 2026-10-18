"""No Docker/model calls: finite diagnostic output and read-only request scope."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import urllib.error
import uuid
from unittest.mock import Mock
import pytest

spec = importlib.util.spec_from_file_location('asset_probe', Path(__file__).parents[1] / 'scripts/diagnose_preview_assets_test.py')
probe = importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
WID = str(uuid.uuid4())
SECRET = 'private-token-value-' * 3


def test_running_probe_never_prints_customer_content_or_token(monkeypatch,capsys):
    private = b'private source content'
    def request(operation, job_id, token, path=None):
        assert job_id == WID and token == SECRET
        if operation == 'status':return {'state':'running'}
        assert operation == 'fetch' and path in probe.PATHS
        return {'status':200,'type':'text/html; charset=utf-8','body':base64.b64encode(private).decode()}
    monkeypatch.setattr(probe,'request',request)
    assert probe.probe(WID,SECRET) == 0
    out = capsys.readouterr().out
    assert SECRET not in out and private.decode() not in out
    rows = [json.loads(line) for line in out.splitlines() if line.startswith('{')]
    assert len(rows) == 5 and rows[0]['state'] == 'running'
    assert all(row['status'] == 200 for row in rows[1:])


def test_stopped_job_is_never_started(monkeypatch,capsys):
    request = Mock(return_value={'state':'stopped'})
    monkeypatch.setattr(probe,'request',request)
    assert probe.probe(WID,SECRET) == 1
    request.assert_called_once_with('status',WID,SECRET)
    assert 'not running' in capsys.readouterr().out


def test_worker_error_is_sanitized_and_other_paths_still_checked(monkeypatch,capsys):
    def request(operation, job_id, token, path=None):
        if operation == 'status':return {'state':'running'}
        if path == '/style.css':raise urllib.error.HTTPError('http://private',503,'private',{},io.BytesIO(b'{"error":"SECRET-RAW-ERROR"}'))
        return {'status':404,'type':'SECRET-MIME','body':base64.b64encode(b'private body').decode()}
    monkeypatch.setattr(probe,'request',request)
    assert probe.probe(WID,SECRET) == 1
    out = capsys.readouterr().out
    assert all(value not in out for value in (SECRET,'SECRET-RAW-ERROR','SECRET-MIME','private body','http://private'))
    assert out.count('worker_asset') == 4 and 'unclassified' in out


def test_only_fixed_loopback_protocol_and_bounded_read(monkeypatch):
    response = Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    response.read.return_value = b'{"state":"running"}'
    open_mock = Mock(return_value=response);monkeypatch.setattr(probe.urllib.request,'urlopen',open_mock)
    probe.request('status',WID,SECRET)
    req = open_mock.call_args.args[0]
    assert req.full_url == 'http://127.0.0.1:8791/v1/status'
    assert req.get_method() == 'POST' and json.loads(req.data) == {'job_id':WID}
    response.read.assert_called_once_with(524289)
    assert open_mock.call_args.kwargs['timeout'] == 20


@pytest.mark.parametrize('job,token',[('../other-job',SECRET),(WID,'short')])
def test_invalid_context_rejected_before_requests(monkeypatch,job,token):
    request=Mock();monkeypatch.setattr(probe,'request',request)
    with pytest.raises(ValueError):probe.probe(job,token)
    request.assert_not_called()
