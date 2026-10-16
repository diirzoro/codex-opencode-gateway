"""Worker archive rejection tests. In-memory only; no extraction or Docker."""
import io
import tarfile
import tempfile
from pathlib import Path
import unittest
from app.services.preview_worker_archive import validate_archive, UnsafePreviewArchive, extract_into_sandbox


def make_archive(names):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name in names:
            content = b"hello"
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    buf.seek(0)
    return tarfile.open(fileobj=buf, mode="r:")


class WorkerArchiveTests(unittest.TestCase):
    def test_accepts_regular_files(self):
        with make_archive(["index.html", "src/app.py"]) as tar:
            self.assertEqual(validate_archive(tar), (2, 10))

    def test_rejects_traversal_absolute_and_private(self):
        for name in ("../etc/passwd", "/etc/passwd", "src/../x", ".env", "src/.env.local", "node_modules/a.js"):
            with self.subTest(name=name), make_archive([name]) as tar:
                with self.assertRaises(UnsafePreviewArchive):
                    validate_archive(tar)

    def test_rejects_duplicates(self):
        with make_archive(["index.html", "index.html"]) as tar:
            with self.assertRaises(UnsafePreviewArchive):
                validate_archive(tar)

    def test_extracts_regular_files_in_empty_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            with make_archive(["index.html", "src/app.py"]) as tar:
                self.assertEqual(extract_into_sandbox(tar, Path(tmp)), (2, 10))
            self.assertEqual((Path(tmp) / "src" / "app.py").read_bytes(), b"hello")

    def test_refuses_nonempty_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "existing").write_text("keep")
            with make_archive(["index.html"]) as tar:
                with self.assertRaises(UnsafePreviewArchive):
                    extract_into_sandbox(tar, Path(tmp))
            self.assertEqual((Path(tmp) / "existing").read_text(), "keep")

    def test_does_not_extract_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            with make_archive(["../escape"]) as tar:
                with self.assertRaises(UnsafePreviewArchive):
                    extract_into_sandbox(tar, Path(tmp))
            self.assertFalse((Path(tmp).parent / "escape").exists())

    def test_rejects_symlink(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo("link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
        buf.seek(0)
        with tarfile.open(fileobj=buf) as tar:
            with self.assertRaises(UnsafePreviewArchive):
                validate_archive(tar)


if __name__ == "__main__":
    unittest.main()
