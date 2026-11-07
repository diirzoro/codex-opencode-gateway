# OpenCode process memory audit — Test first

The reported 4 GB / 1-vCPU VPS currently runs separate OpenCode serve children owned by the Live and Test Gateway processes, plus two opencode web services. These serve children are **not** orphan processes: their parent PIDs are the relevant uvicorn workers. Do not kill them based on age or high RSS.

## Immediate safe diagnosis

Run on VPS as tahir after updating the Test working tree:

```bash
python3 /home/tahir/opencode-gateway-test/backend/scripts/audit_opencode_memory.py
free -h
```

The tool is read-only. It prints PID, parent, RSS, workspace directory and cgroup. No credentials are printed intentionally, but output can still include local workspace paths and must be handled as internal operational data.

## Why not stop opencode web yet?

`backend/app/services/opencode.py::shared_health()` uses `settings.opencode_url`. The Test deployment workflow currently validates `opencode-web-test` and probes `http://127.0.0.1:4097/global/health`. A Web disablement needs a separately reviewed code + health contract + workflow migration and test verification. Do **not** disable Live 4096 or Test 4097 simply because local mode uses child `serve` processes.

## Next implementation gate

Implement a durable idle lifecycle only after determining authoritative signals for agent execution, queued tasks, pending approval/questions, stream connections, and runtime session persistence. Never use process age, browser disappearance, or periodic status polling alone to decide that a child may be stopped. Validate cleanup on Test with a genuinely active agent run and simultaneous workspace traffic. The existing Preview 300s timer applies **only** to isolated Preview processes, not OpenCode agents.

## Current state

No process has been terminated. No VPS change, deployment, or production change has been performed. This audit does not itself reclaim memory.
