"""Worker archive rejection tests. In-memory only; no extraction or Docker."""
import io
import tarfile
import unittest
from app.services.preview_worker_archive import validate_archive, UnsafePreviewArchive


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
