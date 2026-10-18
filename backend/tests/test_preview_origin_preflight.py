"""Read-only inventory parsing/privacy; no real service or network queries."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

spec=importlib.util.spec_from_file_location('preview_preflight',Path(__file__).parents[1]/'scripts/preflight_preview_origin_test.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_only_test_servers_and_safe_loopback_targets_are_reported():
    text='''# config file /etc/nginx/nginx.conf:
    http {
      server {server_name opencode-gateway.codes; proxy_pass http://PRIVATE@127.0.0.1:9000;}
      server {server_name test.opencode-gateway.codes;
        location ~ "x{1,3}" {proxy_set_header Authorization "Bearer SECRET"; proxy_pass http://127.0.0.1:8001/api/;}
        ssl_certificate /etc/letsencrypt/live/test/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/test/privkey.pem;
      }
    }'''
    data=module.selected_servers(text);out=json.dumps(data)
    assert len(data)==1 and data[0]['loopback_upstreams']==['http://127.0.0.1:8001']
    assert 'SECRET' not in out and 'PRIVATE' not in out and ':9000' not in out
    assert 'privkey.pem' in out # file path only, never private key contents


@pytest.mark.parametrize('url',['http://user:SECRET@127.0.0.1:8001','http://10.0.0.5:8001','https://remote.example','http://$unknown'])
def test_unverified_or_credentialed_upstreams_are_not_echoed(url):
    data=module.selected_servers('server {server_name '+module.TEST+'; proxy_pass '+url+';}')
    assert data[0]['loopback_upstreams']==[]
    assert 'SECRET' not in json.dumps(data)


def test_database_url_metadata_never_includes_password_user_or_query():
    data=module.database_metadata('postgresql+psycopg://PRIVATE:SECRET@127.0.0.1:5433/gateway_test?key=TOKEN')
    assert data['test_named'] and data['database']=='gateway_test' and data['port']==5433
    assert all(value not in json.dumps(data) for value in ('PRIVATE','SECRET','TOKEN'))


def test_certificate_coverage_uses_only_public_san(monkeypatch):
    monkeypatch.setattr(module.ssl._ssl,'_test_decode_cert',lambda path:{'subjectAltName':[('DNS','*.opencode-gateway.codes')],'notAfter':'Jan  1 00:00:00 2040 GMT'})
    assert module.certificate_covers('/public/cert.pem',module.PREVIEW)
    assert not module.certificate_covers('/public/cert.pem','nested.preview-test.opencode-gateway.codes')


def test_dns_output_only_contains_parsed_addresses(monkeypatch):
    monkeypatch.setattr(module,'run',lambda *a,**kw:SimpleNamespace(stdout='192.0.2.1 STREAM test\nSECRET invalid\n192.0.2.1 DGRAM test\n'))
    assert module.dns(module.PREVIEW)==['192.0.2.1']



def test_expired_public_certificate_is_not_reported_usable(monkeypatch):
    monkeypatch.setattr(module.ssl._ssl,'_test_decode_cert',lambda path:{'subjectAltName':[('DNS',module.PREVIEW)],'notAfter':'Jan  1 00:00:00 2020 GMT'})
    assert not module.certificate_covers('/public/cert.pem',module.PREVIEW)
