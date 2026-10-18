import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from backend.app.services import workspaces
from backend.app.routes import workspaces as routes


def test_zip_exports_source_without_git_secrets_or_symlink_targets(monkeypatch,tmp_path):
    root=tmp_path/'workspace';root.mkdir();outside=tmp_path/'outside';outside.write_text('outside secret')
    for name in ['index.html','src/app.js','.git/config','.ssh/id_rsa','.env','.env.local','private.key','key.pem']:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name)
    (root/'linked.txt').symlink_to(outside);(root/'linked-dir').symlink_to(tmp_path,target_is_directory=True)
    monkeypatch.setattr(workspaces,'root_for',lambda _:root)
    archive=workspaces.export(SimpleNamespace())
    try:
        with zipfile.ZipFile(archive) as z:
            assert set(z.namelist())=={'index.html','src/app.js'}
            assert z.read('src/app.js')==b'src/app.js'
    finally:archive.unlink()
    assert outside.read_text()=='outside secret' and (root/'index.html').exists()


def test_foreign_export_never_reads_files(monkeypatch):
    monkeypatch.setattr(routes.manager,'owned',Mock(side_effect=HTTPException(404,'Not found')))
    export=Mock();monkeypatch.setattr(routes.manager,'export',export)
    with pytest.raises(HTTPException):routes.export_workspace('foreign',SimpleNamespace(id='other'),Mock())
    export.assert_not_called()
