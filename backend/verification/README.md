# Independent verification

Run from the repository root with the existing application/server environment loaded securely. Do not print or commit that environment or provider keys. No separate database/server or seeded customers are required for these unit regressions.

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/verification -q
node --test backend/verification/runtime-client.test.cjs
node --check app.js
node --check dashboards.js
node --check management.js
node --check runtime-client.js
```

Python regressions use HTTP/process/DB fixtures explicitly; they do not establish successful real provider authentication. Preview fixtures use pytest temporary files. The application configuration still requires its normal database/auth settings even when a test mocks DB work.

Actual runtime evidence, acceptance gaps and one-off browser screenshot procedure are described in [the integration report](../../docs/OPENCODE_INTEGRATION_REPORT.md). Cloud measurement/browser scripts and screenshots are retained under `/workspace/gateway-local/`, outside the source checkout; screenshots are labeled UI fixtures, not real-provider acceptance. The final real-provider run must use an existing real authenticated workspace, real OpenCode, securely configured Gemini/DeepSeek credentials, and no agent override.
