import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock
from pathlib import Path

from validate_migration_chain import validate
import full_test_git_release as release


class MigrationChainTests(unittest.TestCase):
    def check_chain(self, entries):
        with tempfile.TemporaryDirectory() as temp:
            for index, (revision, parent) in enumerate(entries):
                Path(temp, f'{index:04d}.py').write_text(
                    f'revision={revision!r}\ndown_revision={parent!r}\n')
            return validate(temp)

    def test_current_history(self):
        head, count = validate(Path(__file__).resolve().parents[1] / 'backend/alembic/versions')
        self.assertTrue(head)
        self.assertGreater(count, 0)

    def test_future_migration_is_accepted(self):
        self.assertEqual(self.check_chain([('base', None), ('next', 'base'), ('future', 'next')]), ('future', 3))

    def test_invalid_histories_are_rejected(self):
        for entries in ([], [('a', 'missing')], [('a', None), ('a', None)],
                        [('a', None), ('b', None)], [('a', 'b'), ('b', 'a')],
                        [('a', None), ('b', 'c'), ('c', 'b')]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.check_chain(entries)


class TestOnlyAlembicDeployTests(unittest.TestCase):
    def test_existing_service_environment_wins_over_shell_and_file(self):
        """The TEST service's effective DB URL is authoritative."""
        original=os.environ.get("DATABASE_URL")
        class Entry:
            def resolve(self):return release.ROOT/"backend"
            def read_bytes(self):
                return (b"DATABASE_URL=postgresql+psycopg://fixture:secret@localhost/opencode_gateway_test"
                        b"\x00CREDENTIALS_ENCRYPTION_KEY=protected-TEST-key\x00")
        class Proc:
            def stat(self):return SimpleNamespace(st_uid=os.geteuid())
            def joinpath(self,name):
                if name in {"cwd","environ"}:return Entry()
                raise AssertionError(name)
        class ProcRoot:
            def __truediv__(self,pid):
                self_pid=int(pid)
                assert self_pid==12345
                return Proc()
        with patch.object(release,"run",return_value="12345"),patch.object(release,"Path",return_value=ProcRoot()),patch.dict(os.environ,{"DATABASE_URL":"postgresql://user:wrong@localhost/LIVE"}):
            result=release.test_service_environment()
        self.assertIn("/opencode_gateway_test",result["DATABASE_URL"])
        self.assertEqual(result["CREDENTIALS_ENCRYPTION_KEY"],"protected-TEST-key")
        self.assertNotIn("/LIVE",result["DATABASE_URL"])
        self.assertEqual(os.environ.get("DATABASE_URL"),original)

    def test_identity_verification_before_backup(self):
        with patch.object(release,"run") as run:
            release.verified_test_database("test-python",{"DATABASE_URL":"synthetic"})
        args=run.call_args.args
        self.assertEqual(args[:2],("test-python","-c"))
        self.assertIn("SELECT current_database()",args[2])
        self.assertIn("opencode_gateway_test",args[2])

    def test_backup_uses_private_uri_environment_not_command_arguments(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(release,"BACKUP_DIR",Path(temp)/"backups"):
            recorded=[]
            def command(*args,**kwargs):
                recorded.append((args,kwargs))
                if args[0]=="pg_dump":
                    Path(args[args.index("--file")+1]).write_bytes(b"fixture-backup-payload"*8)
                return ""
            env={"DATABASE_URL":"postgresql+psycopg://fixture:SECRET@localhost/opencode_gateway_test"}
            with patch.object(release,"run",side_effect=command):
                path=release.backup_test_database(env)
            self.assertTrue(path.is_file())
            self.assertEqual(path.parent.stat().st_mode&0o777,0o700)
            self.assertEqual([call[0][0] for call in recorded],["pg_dump","pg_restore"])
            self.assertNotIn("SECRET"," ".join(map(str,recorded[0][0])))
            env_used=recorded[0][1]["env"]
            self.assertEqual(env_used["PGDATABASE"],"opencode_gateway_test")
            self.assertEqual(env_used["PGHOST"],"localhost")
            self.assertEqual(env_used["PGUSER"],"fixture")
            self.assertEqual(env_used["PGPASSWORD"],"SECRET")
            self.assertNotIn("SECRET"," ".join(map(str,recorded[0][0])))

    def test_deploy_runs_existing_alembic_without_privileged_migration_runner(self):
        steps=[]
        def command(*args,**kwargs):
            steps.append(args)
            if args[:2]==("systemctl","show"):return "4242"
            return ""
        with patch.object(release,"files",return_value=[]),patch.object(release,"run",side_effect=command),patch.object(release,"service",return_value=True),patch.object(release,"active_revision",return_value="a"*40),patch.object(release,"test_service_environment",return_value={"DATABASE_URL":"synthetic"}),patch.object(release,"test_backend_python",return_value="python-from-test"),patch.object(release,"verified_test_database"),patch.object(release,"backup_test_database"),patch.object(release,"replace"),patch.object(release.time,"sleep"):
            release.rollout("b"*40,"deploy")
        self.assertTrue(any(args[:4]==("python-from-test","-m","alembic","-c") and args[-2:]==("upgrade","head") for args in steps))
        self.assertFalse(any("opencode-gateway-test-migrate" in " ".join(args) for args in steps))

    def test_migration_failure_reports_safe_duplicate_category(self):
        import subprocess
        failure=subprocess.CalledProcessError(1,["python","-m","alembic"],
            stderr=b"RuntimeError: Existing normalized account duplicates require owner reconciliation; email=2")
        with patch.object(release,"run",side_effect=failure):
            with patch("builtins.print") as notice:
                with self.assertRaisesRegex(RuntimeError,"TEST Alembic upgrade failed"):
                    release.apply_test_migrations("python",{"DATABASE_URL":"postgresql://secret"})
        message=" ".join(str(call.args) for call in notice.call_args_list)
        self.assertIn("EXISTING_ACCOUNT_DUPLICATES",message)
        self.assertNotIn("email=2",message)
        self.assertNotIn("secret",message)

    def test_migration_unknown_error_does_not_log_sensitive_stderr(self):
        import subprocess
        failure=subprocess.CalledProcessError(1,["python"],stderr=b"unexpected DATABASE_URL=private-password")
        with patch.object(release,"run",side_effect=failure):
            with patch("builtins.print") as notice:
                with self.assertRaises(RuntimeError):
                    release.apply_test_migrations("python",{})
        self.assertIn("UNCLASSIFIED_ALEMBIC_ERROR",str(notice.call_args.args[0]))
        self.assertNotIn("private-password",str(notice.call_args.args[0]))

    def test_safe_migration_trace_metadata(self):
        import subprocess
        failure=subprocess.CalledProcessError(1,["python"],
            stderr=(b"INFO [alembic.runtime.migration] Running upgrade 0025_email_verification_codes -> 0026_unique_registration_identities, add identities\\n"
                    b"sqlalchemy.exc.ProgrammingError: SECRET=private-password\\nSQLSTATE: 42703\\n"))
        with patch.object(release,"run",side_effect=failure):
            with patch("builtins.print") as notices:
                with self.assertRaises(RuntimeError):
                    release.apply_test_migrations("python",{})
        printed=" ".join(str(c.args) for c in notices.call_args_list)
        self.assertIn("ProgrammingError",printed)
        self.assertIn("0026_unique_registration_identities",printed)
        self.assertIn("42703",printed)
        self.assertNotIn("private-password",printed)

    def test_audit_does_not_connect_to_database(self):
        with patch.object(release,"files",return_value=[]),patch.object(release,"test_service_environment",side_effect=AssertionError("DB reached")),patch.object(release,"run",side_effect=AssertionError("command reached")):
            release.rollout("a"*40,"audit")


if __name__ == '__main__':
    unittest.main()
