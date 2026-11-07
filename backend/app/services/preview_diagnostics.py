"""Finite, credential-free Preview failure codes shared by worker and Gateway."""
MESSAGES = {
    'worker_operation_failed': 'Preview worker operation failed; run the TEST worker diagnostic',
    'docker_binary_missing': 'Docker executable is not available to the Preview worker',
    'docker_socket_permission_denied': 'Preview worker cannot access its dedicated Docker socket',
    'docker_daemon_unreachable': 'The dedicated Preview Docker daemon is not reachable',
    'docker_resource_limits_unavailable': 'Docker cannot enforce the required cgroup resource limits',
    'docker_isolation_unavailable': 'Docker could not establish the required sandbox isolation',
    'docker_snapshot_mount_denied': 'Docker cannot mount the worker-owned source snapshot',
    'docker_image_unavailable': 'The pinned runtime image is not present in the dedicated daemon',
    'docker_job_conflict': 'A sandbox with this Preview job name already exists',
    'docker_operation_timed_out': 'The Preview Docker operation exceeded its deadline',
    'docker_operation_failed': 'Docker rejected the operation; inspect the dedicated TEST worker diagnostics',
    'invalid_container_spec': 'The fixed sandbox image, entrypoint or mount contract is invalid',
    'application_entrypoint_missing': 'The runtime image or prepared project lacks the application entrypoint',
    'application_not_ready': 'The application did not answer on internal port 8080 before the readiness deadline',
    'application_exited_early': 'The application container exited before answering on internal port 8080',
    'dependency_preparation_required': 'This framework requires isolated dependency preparation; no verified dependency stage is configured',
}


def docker_failure_code(stderr):
    """Classify locally; never expose raw daemon output, paths, commands or logs."""
    text = stderr.lower() if isinstance(stderr, str) else ''
    if 'permission denied' in text and ('docker.sock' in text or 'docker daemon socket' in text):
        return 'docker_socket_permission_denied'
    if 'cannot connect to the docker daemon' in text or 'is the docker daemon running' in text:
        return 'docker_daemon_unreachable'
    if any(term in text for term in ('cgroup', 'cpu quota', 'memory limit', 'pids limit', 'cpu.cfs', 'cpuset')):
        return 'docker_resource_limits_unavailable'
    if any(term in text for term in ('mounts denied', 'error while creating mount source', 'invalid mount config', 'mount source path does not exist')):
        return 'docker_snapshot_mount_denied'
    if any(term in text for term in ('no such image', 'pull access denied', 'image is not present locally', 'unable to find image')):
        return 'docker_image_unavailable'
    if 'container name' in text and 'already in use' in text:
        return 'docker_job_conflict'
    if 'executable file not found' in text or ('no such file' in text and any(term in text for term in ('stat ./node_modules', 'exec:'))):
        return 'application_entrypoint_missing'
    if any(term in text for term in ('operation not permitted', 'seccomp', 'apparmor', 'failed to create shim', 'failed to create task')):
        return 'docker_isolation_unavailable'
    return 'docker_operation_failed'
