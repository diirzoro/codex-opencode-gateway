"""Pure sandbox-command tests: Docker is never launched."""
import unittest
from app.services.preview_container_spec import ContainerSpec, UnsafeContainerSpec, argv_for

DIGEST = "sha256:" + "a" * 64


class ContainerSpecTests(unittest.TestCase):
    def test_fixed_limits_and_no_public_ports(self):
        args = argv_for(ContainerSpec(DIGEST, ("python", "-m", "http.server", "8080"),
                                      "/var/lib/preview-worker/jobs/abc/src"))
        self.assertIn("--read-only", args)
        self.assertIn("--cap-drop", args)
        self.assertIn("none", args)
        self.assertNotIn("--privileged", args)
        self.assertNotIn("-p", args)
        self.assertNotIn("/var/run/docker.sock", " ".join(args))
        self.assertEqual(args[-3:], ("-m", "http.server", "8080"))

    def test_rejects_unpinned_image(self):
        with self.assertRaises(UnsafeContainerSpec):
            argv_for(ContainerSpec("python:latest", ("python",), "/var/lib/preview-worker/jobs/a/src"))

    def test_rejects_mount_option_injection(self):
        for path in (
            "/var/lib/preview-worker/jobs/a/src,consistency=delegated",
            "/var/lib/preview-worker/jobs/a/../src",
            "/var/lib/preview-worker/jobs/a/src/extra",
        ):
            with self.subTest(path=path), self.assertRaises(UnsafeContainerSpec):
                argv_for(ContainerSpec(DIGEST, ("python",), path))

    def test_rejects_untrusted_mount(self):
        with self.assertRaises(UnsafeContainerSpec):
            argv_for(ContainerSpec(DIGEST, ("python",), "/etc/src"))


if __name__ == "__main__":
    unittest.main()
