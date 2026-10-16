"""No Docker process is launched by these contract tests."""
import subprocess
import unittest
from app.services.preview_container_spec import ContainerSpec
from app.services.preview_docker_provisioner import DockerProvisioner, PreviewProvisioningError

DIGEST = "docker.io/library/python@sha256:" + "a" * 64
CID = "b" * 64
MOUNT = "/var/lib/preview-worker/jobs/job1/src"


class DockerAdapterTests(unittest.TestCase):
    def test_launch_is_detached_unprivileged_and_network_none(self):
        calls = []
        def fake(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, CID)
        worker = DockerProvisioner(run=fake)
        output = worker.launch_smoke("job1", ContainerSpec(DIGEST, ("python", "-V"), MOUNT))
        self.assertEqual(output, CID)
        args = calls[0]
        self.assertIn("--detach", args)
        self.assertIn("--network", args)
        self.assertIn("none", args)
        self.assertIn("--read-only", args)
        self.assertNotIn("-p", args)

    def test_cannot_cross_job_mount(self):
        def never(*args, **kwargs):
            self.fail("Docker must not be called")
        worker = DockerProvisioner(run=never)
        with self.assertRaises(PreviewProvisioningError):
            worker.launch_smoke("other", ContainerSpec(DIGEST, ("python",), MOUNT))

    def test_stop_refuses_foreign_container(self):
        calls = []
        def fake(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "different")
        worker = DockerProvisioner(run=fake)
        with self.assertRaises(PreviewProvisioningError):
            worker.stop(CID, "job1")
        self.assertEqual(len(calls), 1)

    def test_owned_stop(self):
        calls = []
        def fake(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0,
                                               "job1" if "inspect" in args else CID)
        worker = DockerProvisioner(run=fake)
        worker.stop(CID, "job1")
        self.assertEqual(calls[-1][1], "stop")


if __name__ == "__main__":
    unittest.main()
