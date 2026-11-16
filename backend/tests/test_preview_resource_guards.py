"""Resource lifecycle tests; never contact Docker or execute project code."""
from app.services.preview_worker_server import WorkerServer
from app.services.preview_docker_provisioner import PreviewProvisioningError

class FakeDocker:
    def __init__(self):
        self.stopped = []
        self.orphans = ()
        self.fail = False
    def managed_containers(self):
        return self.orphans
    def stop(self, cid, job_id):
        if self.fail:
            raise PreviewProvisioningError('unavailable')
        self.stopped.append((job_id, cid))

def worker(jobs, now=301):
    docker = FakeDocker()
    server = WorkerServer(('127.0.0.1', 0), 'x'*32, docker,
                          jobs=jobs, clock=lambda: now, admission=lambda: True)
    return server, docker

def job(start=0, activity=0):
    return dict(container_id='a'*64, state='running',
                started_monotonic=start, activity_monotonic=activity)

def test_idle_preview_stops_and_releases_allocation():
    jobs = {'first': job()}
    server, docker = worker(jobs)
    try:
        server.reap_expired()
        assert jobs['first']['container_id'] is None
        assert jobs['first']['stop_reason'] == 'idle_timeout'
        assert len(docker.stopped) == 1
    finally:
        server.server_close()

def test_recent_activity_cannot_extend_hard_deadline():
    jobs = {'first': job(activity=899)}
    server, docker = worker(jobs, now=900)
    try:
        server.reap_expired()
        assert jobs['first']['stop_reason'] == 'runtime_limit'
    finally:
        server.server_close()

def test_failed_cleanup_keeps_slot_until_retry_succeeds():
    jobs = {'first': job()}
    server, docker = worker(jobs)
    try:
        docker.fail = True
        server.reap_expired()
        assert jobs['first']['container_id']
        assert jobs['first']['state'] == 'stopping'
        docker.fail = False
        server.reap_expired()
        assert jobs['first']['container_id'] is None
    finally:
        server.server_close()

def test_reconcile_only_unknown_owned_jobs_once():
    jobs = {'first': job(activity=301)}
    server, docker = worker(jobs)
    try:
        docker.orphans = (('first', 'a'*64), ('orphan', 'b'*64))
        server.reconcile_orphans()
        server.reconcile_orphans()
        assert docker.stopped == [('orphan', 'b'*64)]
    finally:
        server.server_close()

def test_shutdown_stops_active_preview():
    server, docker = worker({'first': job(activity=301)})
    server.server_close()
    assert docker.stopped == [('first', 'a'*64)]


def test_start_denied_while_another_preview_is_allocated():
    import json
    import urllib.request
    import urllib.error
    from threading import Thread
    from types import SimpleNamespace
    jobs = {'first': job(activity=301), 'second': dict(
        state='ready', container_id=None,
        spec=SimpleNamespace(argv=('node', 'server.js')))}
    server, docker = worker(jobs)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f'http://127.0.0.1:{server.server_address[1]}/v1/start',
            data=json.dumps({'job_id': 'second'}).encode(),
            headers={'Authorization': 'Bearer '+'x'*32})
        try:
            urllib.request.urlopen(request)
            assert False, 'start must be refused'
        except urllib.error.HTTPError as exc:
            assert exc.code == 409
            assert json.load(exc)['error'] == 'preview_capacity_reached'
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_polling_does_not_extend_idle_time():
    import json
    import urllib.request
    from threading import Thread
    jobs = {'first': job(activity=300)}
    server, docker = worker(jobs, now=301)
    docker.status = lambda cid, job_id: 'running'
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f'http://127.0.0.1:{server.server_address[1]}/v1/status',
            data=json.dumps({'job_id': 'first'}).encode(),
            headers={'Authorization': 'Bearer '+'x'*32})
        with urllib.request.urlopen(request) as response:
            assert json.load(response)['state'] == 'running'
        assert jobs['first']['activity_monotonic'] == 300
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
