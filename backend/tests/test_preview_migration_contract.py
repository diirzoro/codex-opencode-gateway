"""Check Preview lease migration matches ORM and creates only Preview tables.

This suite does not connect to production or Test PostgreSQL.
"""
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, inspect
from sqlalchemy.schema import CreateTable

from app.models.preview import PreviewRuntimeLease
from app.models.workspace import WorkspaceSession
from alembic.versions import __path__ as _versions_path
import importlib.util
from pathlib import Path

MIGRATION = Path(next(iter(_versions_path))) / "0019_preview_runtime_leases.py"


class PreviewMigrationContractTests(unittest.TestCase):
    def test_migration_follows_verified_head(self):
        spec = importlib.util.spec_from_file_location("preview_migration_0019", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0019_preview_runtime_leases")
        self.assertEqual(module.down_revision, "0018_email_verification")

    def test_orm_sql_compiles_without_open_code_session_dependency(self):
        table = PreviewRuntimeLease.__table__
        rendered = str(CreateTable(table).compile(dialect=create_engine("sqlite://").dialect))
        self.assertIn("preview_runtime_leases", rendered)
        self.assertIn("workspace_id", rendered)
        self.assertNotIn("opencode_session_id", rendered)
        self.assertEqual(WorkspaceSession.__tablename__, "workspace_sessions")

    def test_migration_matches_orm_columns(self):
        spec = importlib.util.spec_from_file_location("preview_migration_0019", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        captured = {}
        def create_table(name, *columns, **kwargs):
            captured["name"] = name
            captured["columns"] = {c.name for c in columns if hasattr(c, "name") and c.name is not None}
        with patch.object(module.op, "create_table", create_table), patch.object(module.op, "create_index"):
            module.upgrade()
        self.assertEqual(captured["name"], PreviewRuntimeLease.__tablename__)
        self.assertEqual(captured["columns"], set(PreviewRuntimeLease.__table__.columns.keys()))


if __name__ == "__main__":
    unittest.main()
