# Current local update — 2026-10-04

Management additions: PUT /api/account/password; POST /api/auth/forgot-password and /reset-password; POST /api/account/lifecycle; GET /api/account/sessions; DELETE /api/account/sessions/{id}; GET /api/account/logs; GET/POST /api/billing/methods; PUT/DELETE /api/billing/methods/{id}; GET /api/billing/available-methods; GET /api/admin/logs and /connections; DELETE /api/admin/connections/{user_id}; PUT /api/admin/users/{user_id}/role; GET/POST /api/admin/locations/{kind}; PUT/DELETE /api/admin/locations/{kind}/{id}. platform=true selects admin payment scope; DELETE location disables it. Password inputs are current_password/new_password; recovery uses email then token/password; lifecycle uses action/password/confirmation. All account APIs require authentication except generic recovery request and token-authorized reset. See OpenAPI /docs for field schemas. GitHub callbacks now require code and verified membership.

See [PHASE_REPORT.md](PHASE_REPORT.md) and [ACCOUNT_WORKSPACE_REQUIREMENTS.md](ACCOUNT_WORKSPACE_REQUIREMENTS.md).

---

## Earlier audit (historical)

# API reference

Updated 2026-10-03. Current local implementation; no deployment claim. Same-origin browser requests use an opaque HttpOnly SameSite=Strict cookie. Session tokens are never returned in JSON. `Secure=true` is the default; only local HTTP testing sets false. Mutating cross-site Origin / Fetch Metadata requests are rejected.

## Gateway routes

All routes below are implemented, but a guarded unavailable response is not a working integration. Auth/health/locations are public as appropriate; all project/workspace/session/provider/GitHub/OpenCode routes require a current active account. Object routes additionally filter owner and return 404 for another owner's identifier. Admin routes require admin or owner.

| Method | Path | Request schema | Handler |
|---|---|---|---|
| GET | `/api/admin/overview` | `—` | Overview |
| GET | `/api/admin/users` | `—` | Users |
| POST | `/api/auth/login` | `LoginRequest` | Login |
| POST | `/api/auth/logout` | `—` | Logout |
| GET | `/api/auth/me` | `—` | Me |
| POST | `/api/auth/register` | `RegisterRequest` | Register |
| GET | `/api/github/status` | `—` | Github Status |
| GET | `/api/health` | `—` | Health |
| GET | `/api/locations/countries` | `—` | Countries |
| GET | `/api/locations/countries/{country_id}/regions` | `—` | Regions |
| GET | `/api/locations/regions/{region_id}/cities` | `—` | Cities |
| GET | `/api/opencode/health` | `—` | Health |
| GET | `/api/opencode/status` | `—` | Runtime Status |
| GET | `/api/profile` | `—` | Get Profile |
| PATCH | `/api/profile` | `ProfilePatch` | Patch Profile |
| GET | `/api/projects` | `—` | Projects |
| POST | `/api/projects` | `CreateProject` | Create Project |
| GET | `/api/projects/{project_id}` | `—` | Project |
| PATCH | `/api/projects/{project_id}` | `RenameProject` | Rename |
| DELETE | `/api/projects/{project_id}` | `—` | Delete Project |
| GET | `/api/sessions/{session_id}` | `—` | Session |
| GET | `/api/sessions/{session_id}/events` | `—` | Events |
| POST | `/api/sessions/{session_id}/messages` | `MessageRequest` | Send |
| GET | `/api/sessions/{session_id}/messages` | `—` | Messages |
| GET | `/api/sessions/{session_id}/permissions` | `—` | Permissions |
| POST | `/api/sessions/{session_id}/permissions/{permission_id}` | `Approval` | Approve |
| POST | `/api/sessions/{session_id}/stop` | `—` | Stop |
| GET | `/api/templates` | `—` | Templates |
| GET | `/api/workspaces` | `—` | Workspaces |
| POST | `/api/workspaces` | `CreateProject` | Create Workspace |
| GET | `/api/workspaces/{workspace_id}` | `—` | Workspace |
| DELETE | `/api/workspaces/{workspace_id}` | `—` | Delete Workspace |
| GET | `/api/workspaces/{workspace_id}/changes` | `—` | Changes |
| GET | `/api/workspaces/{workspace_id}/diff` | `—` | Diff |
| GET | `/api/workspaces/{workspace_id}/files` | `—` | Files |
| GET | `/api/workspaces/{workspace_id}/files/content` | `—` | File Content |
| POST | `/api/workspaces/{workspace_id}/git/commit` | `CommitRequest` | Commit |
| POST | `/api/workspaces/{workspace_id}/git/push` | `—` | Push |
| GET | `/api/workspaces/{workspace_id}/git/status` | `—` | Git Status |
| GET | `/api/workspaces/{workspace_id}/logs` | `—` | Logs |
| GET | `/api/workspaces/{workspace_id}/providers` | `—` | Available Providers |
| POST | `/api/workspaces/{workspace_id}/sessions` | `NewSession` | New Session |
| GET | `/api/workspaces/{workspace_id}/sessions` | `—` | Sessions |

## Main contracts

`POST /api/projects` (alias `/api/workspaces`) accepts `{ "project_name":"My project", "source_type":"blank" }` or `source_type:"template", template:"html"|"python"|"node"`. It returns 201 `{project,workspace}`. Project contains id/name/source_type/repository/branch/template/created_at. Workspace contains id/project_id/status/base_commit_sha/created_at/last_activity_at; no physical path. GitHub creation returns 503 without cloning. Extra fields are rejected. PATCH project accepts `{name}`. Delete project/workspace returns 409 preserving files.

File list `?path=` returns `{name,path,type}[]`, relative paths only, max 1000 entries. Content `?path=` returns `{path,content}`, at most 1 MB UTF-8, binary 415. Changes returns Git status entries. Diff returns `{diff,truncated}` with 1 MB output cap. Git status returns `{branch,head,changes,clean,push_available:false}`. Commit accepts `{message}` and returns actual status; push returns 503 with no attempt. Logs are the last 200 persisted Gateway event metadata rows `{id,type,created_at}`, not raw process output or test results.

New session accepts `{title}` and returns 201 `{id,workspace_id,title,status,created_at}` only after OpenCode creates a real session. Runtime-disabled requests return 503 and do not create fake records. Providers returns safe actual provider/model/auth-method metadata; no credential values. Message accepts `{text,provider_id,model_id}`, returns 202 submitted after connected-provider/model checks. That acknowledges submission, not successful execution. GET messages returns text parts only; rich tool outputs and token streaming are not yet implemented.

SSE events use `id`, `event`, JSON `data`; support `Last-Event-ID` or `?after=`. Gateway events: submitted, waiting_approval, approval_decision, completed, failed, cancelled. Durable event rows support replay; tasks remain in-process and are not restart-safe. Stop forwards actual abort and only reports cancellation after a true response. Approval listing returns `{id,permission,patterns,reviewable}` for the current runtime session. Reply accepts only `once` or `reject`; incomplete/overlong details cannot be approved. No blind approval and no `always` endpoint. Cross-owner permission IDs return 404.

Errors: 401 unauthenticated/expired, 403 authorization or unsafe path, 404 unknown/unowned, 409 conflicting state/preserved deletion, 413 preview size, 415 binary, 422 input, 502 invalid runtime response, 503 unavailable runtime/integration. Runtime errors do not serialize raw stderr, secrets or host paths.

## Installed OpenCode contract

Verified against local OpenCode **1.18.31**, `/global/health` and `/doc` captured from an isolated process on 2026-10-03. Server calls use Basic auth and `directory=<owned repo>` query. The adapter refuses unverified versions. Browser never receives runtime URL, password or session ID.

| OpenCode request | Shape / use |
|---|---|
| GET /global/health | `{healthy:true,version:"1.18.31"}` |
| POST /session | `{title,permission:[{permission:"*",pattern:"*",action:"ask"},{permission:"external_directory",pattern:"*",action:"deny"}]}` → session object with `id` |
| GET /session/{id}/message | Message list with `info` and `parts`; Gateway renders text parts |
| POST /session/{id}/message | `{parts:[{type:"text",text}],model:{providerID,modelID}}` → completed message; background Gateway task |
| POST /session/{id}/abort | Boolean acknowledgement |
| GET /permission | Pending requests with sessionID/id/permission/patterns |
| POST /permission/{requestID}/reply | `{reply:"once"|"reject"}` → boolean acknowledgement |
| GET /provider | `{all,connected,default}`; available models under provider.models |
| GET /provider/auth | Actual available auth methods; discovery only |

Installed schema also exposes `/event`, `/session/{id}/prompt_async`, `/auth/{providerID}` and provider OAuth routes; they are **not** implemented as complete Gateway authentication/tool-stream features. Official references: https://opencode.ai/docs/server/ and https://opencode.ai/docs/permissions/ .

## Missing target APIs

GitHub App installation/callback/repos/branches/webhooks; provider credential connect/test/delete/OAuth callbacks; publish-to-GitHub; upload/preview; recovery/idempotency; plan/version/payment/receipt/ledger mutations; full administrative audit/roles. Do not treat route names in the requirements as implemented.

## Exact request schemas

### Approval

```json
{
  "properties": {
    "reply": {
      "type": "string",
      "pattern": "^(once|reject)$",
      "title": "Reply"
    }
  },
  "type": "object",
  "required": [
    "reply"
  ],
  "title": "Approval"
}
```

### CommitRequest

```json
{
  "properties": {
    "message": {
      "type": "string",
      "maxLength": 500,
      "minLength": 1,
      "pattern": "^[^\\x00]+$",
      "title": "Message"
    }
  },
  "type": "object",
  "required": [
    "message"
  ],
  "title": "CommitRequest"
}
```

### CreateProject

```json
{
  "properties": {
    "project_name": {
      "type": "string",
      "maxLength": 120,
      "minLength": 1,
      "pattern": "^[^\\r\\n\\x00]+$",
      "title": "Project Name"
    },
    "source_type": {
      "type": "string",
      "enum": [
        "github",
        "blank",
        "template"
      ],
      "title": "Source Type",
      "default": "blank"
    },
    "repository": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Repository"
    },
    "branch": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Branch"
    },
    "template": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Template"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "project_name"
  ],
  "title": "CreateProject"
}
```

### LoginRequest

```json
{
  "properties": {
    "identity": {
      "type": "string",
      "maxLength": 254,
      "minLength": 3,
      "title": "Identity"
    },
    "password": {
      "type": "string",
      "maxLength": 128,
      "minLength": 1,
      "title": "Password"
    }
  },
  "type": "object",
  "required": [
    "identity",
    "password"
  ],
  "title": "LoginRequest"
}
```

### MessageRequest

```json
{
  "properties": {
    "text": {
      "type": "string",
      "maxLength": 20000,
      "minLength": 1,
      "title": "Text"
    },
    "provider_id": {
      "type": "string",
      "maxLength": 120,
      "minLength": 1,
      "pattern": "^[A-Za-z0-9_.-]+$",
      "title": "Provider Id"
    },
    "model_id": {
      "type": "string",
      "maxLength": 200,
      "minLength": 1,
      "title": "Model Id"
    }
  },
  "type": "object",
  "required": [
    "text",
    "provider_id",
    "model_id"
  ],
  "title": "MessageRequest"
}
```

### NewSession

```json
{
  "properties": {
    "title": {
      "type": "string",
      "maxLength": 120,
      "minLength": 1,
      "title": "Title",
      "default": "New session"
    }
  },
  "type": "object",
  "title": "NewSession"
}
```

### ProfilePatch

```json
{
  "properties": {
    "phone": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 30,
          "minLength": 6
        },
        {
          "type": "null"
        }
      ],
      "title": "Phone"
    },
    "postal_code": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 24,
          "minLength": 2
        },
        {
          "type": "null"
        }
      ],
      "title": "Postal Code"
    },
    "country_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Country Id"
    },
    "region_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Region Id"
    },
    "city_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "City Id"
    },
    "preferred_language": {
      "anyOf": [
        {
          "type": "string",
          "pattern": "^(ar|en)$"
        },
        {
          "type": "null"
        }
      ],
      "title": "Preferred Language"
    },
    "preferred_theme": {
      "anyOf": [
        {
          "type": "string",
          "pattern": "^(light|dark)$"
        },
        {
          "type": "null"
        }
      ],
      "title": "Preferred Theme"
    }
  },
  "type": "object",
  "title": "ProfilePatch"
}
```

### RegisterRequest

```json
{
  "properties": {
    "username": {
      "type": "string",
      "maxLength": 50,
      "minLength": 6,
      "pattern": "^[A-Za-z0-9_.-]+$",
      "title": "Username"
    },
    "email": {
      "type": "string",
      "format": "email",
      "title": "Email"
    },
    "password": {
      "type": "string",
      "maxLength": 128,
      "minLength": 8,
      "title": "Password"
    },
    "phone": {
      "type": "string",
      "maxLength": 30,
      "minLength": 6,
      "title": "Phone"
    },
    "postal_code": {
      "type": "string",
      "maxLength": 24,
      "minLength": 2,
      "title": "Postal Code"
    },
    "country_id": {
      "type": "integer",
      "title": "Country Id"
    },
    "region_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Region Id"
    },
    "city_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "City Id"
    }
  },
  "type": "object",
  "required": [
    "username",
    "email",
    "password",
    "phone",
    "postal_code",
    "country_id"
  ],
  "title": "RegisterRequest"
}
```

### RenameProject

```json
{
  "properties": {
    "name": {
      "type": "string",
      "maxLength": 120,
      "minLength": 1,
      "pattern": "^[^\\r\\n\\x00]+$",
      "title": "Name"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "name"
  ],
  "title": "RenameProject"
}
```

### UserOut

```json
{
  "properties": {
    "id": {
      "type": "string",
      "title": "Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "email": {
      "type": "string",
      "title": "Email"
    },
    "phone": {
      "type": "string",
      "title": "Phone"
    },
    "postal_code": {
      "type": "string",
      "title": "Postal Code"
    },
    "country": {
      "type": "string",
      "title": "Country"
    },
    "region": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Region"
    },
    "city": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City"
    },
    "role": {
      "type": "string",
      "title": "Role"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "preferred_language": {
      "type": "string",
      "title": "Preferred Language"
    },
    "preferred_theme": {
      "type": "string",
      "title": "Preferred Theme"
    },
    "trial_started_at": {
      "type": "string",
      "format": "date-time",
      "title": "Trial Started At"
    },
    "trial_ends_at": {
      "type": "string",
      "format": "date-time",
      "title": "Trial Ends At"
    },
    "trial_remaining_days": {
      "type": "integer",
      "title": "Trial Remaining Days"
    },
    "last_login_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Last Login At"
    }
  },
  "type": "object",
  "required": [
    "id",
    "username",
    "email",
    "phone",
    "postal_code",
    "country",
    "region",
    "city",
    "role",
    "status",
    "preferred_language",
    "preferred_theme",
    "trial_started_at",
    "trial_ends_at",
    "trial_remaining_days",
    "last_login_at"
  ],
  "title": "UserOut"
}
```


## Registration policy update — 2026-10-04

New usernames require 6–50 ASCII letters/digits/underscore/dot/hyphen. New passwords require 8–128 characters with at least one ASCII number and one punctuation symbol (e.g. ! or @). No uppercase or letter requirement; spaces do not count as symbols. Existing login remains valid and is not revalidated against registration constraints. Frontend hints/errors use Arabic/English and match backend validation. No migration is needed.
