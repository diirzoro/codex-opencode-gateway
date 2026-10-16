"""Preview lease ORM schema checks; no production DB migrations executed."""
import unittest
from app.models.preview import PreviewRuntimeLease
from sqlalchemy import UniqueConstraint


class PreviewModelContractTests(unittest.TestCase):
    def test_preview_leases_are_separate_from_agent_sessions(self):
        self.assertEqual(PreviewRuntimeLease.__tablename__, "preview_runtime_leases")
        cols = PreviewRuntimeLease.__table__.columns
        for column in ("workspace_id", "user_id", "state", "worker_id", "generation", "last_user_activity_at"):
            self.assertIn(column, cols)
        self.assertNotIn("opencode_session_id", cols)
        self.assertNotIn("provider_token", cols)

    def test_workspace_is_unique_per_lease(self):
        self.assertTrue(any(isinstance(item, UniqueConstraint) and\n                            {col.name for col in item.columns} == {"workspace_id"}\n                            for item in PreviewRuntimeLease.__table__.constraints))

if __name__ == "__main__":
    unittest.main()
