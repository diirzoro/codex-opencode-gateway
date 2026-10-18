"""Lockfile discovery never launches an executable or installs dependencies."""
import tempfile
import unittest
from pathlib import Path

from app.services.preview_package_manager import detect


class PreviewPackageManagerTests(unittest.TestCase):
    def test_npm_and_alternatives(self):
        for manager, name in (("npm", "package-lock.json"), ("pnpm", "pnpm-lock.yaml"),
                              ("yarn", "yarn.lock"), ("bun", "bun.lockb")):
            with self.subTest(manager=manager), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "package.json").write_text('{"scripts":{"build":"echo safe"}}')
                (root / name).write_text("lockfile")
                result = detect(root)
                self.assertEqual(result["package_manager"], manager)
                self.assertTrue(result["installation_ready"])

    def test_missing_lockfile_is_not_installable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text("{}")
            result = detect(root)
            self.assertFalse(result["installation_ready"])

    def test_ambiguous_lockfiles_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("package.json", "package-lock.json", "pnpm-lock.yaml"):
                (root / name).write_text("{}")
            result = detect(root)
            self.assertIsNone(result["package_manager"])
            self.assertFalse(result["installation_ready"])

    def test_missing_manifest_prevents_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package-lock.json").write_text("{}")
            self.assertFalse(detect(root)["installation_ready"])


if __name__ == "__main__":
    unittest.main()
