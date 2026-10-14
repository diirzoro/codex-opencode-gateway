"""Fail-closed preview control plane. No customer code or engine is invoked.

Plans are advisory inputs to a future dedicated runner, never shell commands on
this host. Execution remains unavailable until an isolated runner is verified.
"""
from . import preview

# Fixed security contract: clients cannot loosen these limits via API input.
LIMITS={"cpu_cores":1,"memory_mb":512,"disk_mb":512,"processes":128,
        "execution_seconds":900,"log_bytes":100000,"uid":10001,
        "read_only_root":True,"drop_capabilities":["ALL"],"no_new_privileges":True,
        "network":"none","public_ports":[],"docker_socket":False,
        "host_secrets":False,"source_mount":"owned_snapshot_read_only",
        "writable_storage":"size_limited_ephemeral"}


def plan(workspace):
    detected=preview.detect(workspace)
    framework=detected['framework']
    web=framework in {'html','nextjs','vite','angular','nuxt','svelte','react','vue','node','django','laravel','python','php'}
    family='node' if framework in {'nextjs','vite','angular','nuxt','svelte','react','vue','node'} else 'python' if framework in {'django','python'} else 'php' if framework in {'laravel','php'} else None
    return {"framework":framework,"mode":"static" if framework=='html' else "isolated_runner_required",
            "runtime_family":family,"web_candidate":web,
            "state":"static_available" if framework=='html' else "blocked",
            "execution_enabled":False,"limits":dict(LIMITS),
            "routing":{"authentication_required":True,"tenant_and_project_bound":True,
                       "separate_origin_required":True,"host_port_exposure":False},
            "blockers":[] if framework=='html' else ["A dedicated isolated runner and authenticated separate-origin routing are not configured or verified.",
                "Build dependencies require a separately controlled preparation stage; runtime egress must remain restricted."],
            "message":"No project code was executed. Non-web projects need a supported output/log runner." if not web else "No application server was started."}
