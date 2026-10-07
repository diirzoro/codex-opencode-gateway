"""Read-only preview boundary checks; temporary filesystem fixtures, no customer DB."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.services import preview, workspaces


def test_preview_embeds_local_assets_and_blocks_network(monkeypatch, tmp_path):
    monkeypatch.setattr(workspaces, 'root_for', lambda _: tmp_path)
    (tmp_path/'index.html').write_text('<link rel="stylesheet" href="style.css"><h1>Project</h1><script src="main.js"></script><img src="icon.png">')
    (tmp_path/'style.css').write_text('h1{color:blue}')
    (tmp_path/'main.js').write_text('document.title="Project";')
    (tmp_path/'icon.png').write_bytes(b'image-fixture')
    result=preview.render(SimpleNamespace())
    assert 'h1{color:blue}' in result['html']
    assert 'document.title=' in result['html']
    assert 'data:image/png;base64,' in result['html']
    assert "connect-src 'none'" in result['html']
    assert "base-uri 'none'" in result['html']
    assert result['browser_automation'] is False


@pytest.mark.parametrize('asset', ['../secret.js', '.env', '.git/config', 'linked.js'])
def test_preview_rejects_private_and_escaping_assets(monkeypatch, tmp_path, asset):
    monkeypatch.setattr(workspaces, 'root_for', lambda _: tmp_path)
    (tmp_path/'index.html').write_text('<script src="'+asset+'"></script>')
    (tmp_path/'linked.js').symlink_to(tmp_path.parent/'outside.js')
    with pytest.raises(HTTPException) as error:preview.render(SimpleNamespace())
    assert error.value.status_code==403
