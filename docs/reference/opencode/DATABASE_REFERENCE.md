# Database reference

Updated 2026-10-03. SQLAlchemy models are runtime authority. PostgreSQL is the application target; SQLite is explicitly test-only. No customer repository source content or raw authentication token is stored in Gateway PostgreSQL.

## Migrations

- `0001_accounts`: users/auth_sessions/countries/regions/cities, initial location seed.
- `0002_workspaces`: projects/workspaces/workspace_sessions/execution_events. No destructive alteration of account tables. Downgrade drops new tables and would lose their metadata; do not use on valuable work.

Fresh SQLite migration `alembic upgrade head` and `alembic current` verified at 0002_workspaces. PostgreSQL offline SQL generated successfully, but not executed on PostgreSQL 16. No production database was inspected or migrated.

## Current tables

### countries

| Column | Type | Nullable | Key / reference |
|---|---|---|---|
| id | INTEGER | False | PK  |
| name | VARCHAR(120) | False |  |
| code | VARCHAR(2) | False |  |
| enabled | BOOLEAN | False |  |

### regions

| Column | Type | Nullable | Key / reference |
|---|---|---|---|
| id | INTEGER | False | PK  |
| country_id | INTEGER | False | countries.id |
| name | VARCHAR(120) | False |  |
| enabled | BOOLEAN | False |  |

### cities

| Column | Type | Nullable | Key / reference |
|---|---|---|---|
| id | INTEGER | False | PK  |
| region_id | INTEGER | False | regions.id |
| name | VARCHAR(120) | False |  |
| enabled | BOOLEAN | False |  |

### users

| Column | Type | Nullable | Key / reference |
|---|---|---|---|
| id | CHAR(32) | False | PK  |
| username | VARCHAR(50) | False |  |
| email | VARCHAR(254) | False |  |
| password_hash | VARCHAR(255) | False |  |
| phone | VARCHAR(30) | False |  |
| postal_code | VARCHAR(24) | False |  |
| country_id | INTEGER | False | countries.id |
| region_id | INTEGER | True | regions.id |
| city_id | INTEGER | True | cities.id |
| role | VARCHAR(20) | False |  |
| status | VARCHAR(20) | False |  |
| preferred_language | VARCHAR(5) | False |  |
| preferred_theme | VARCHAR(10) | False |  |
| trial_started_at | DATETIME | False |  |
| trial_ends_at | DATETIME | False |  |
| last_login_at | DATETIME | True |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

### auth_sessions

| Column | Type | Nullable | Key / reference |
|---|---|---|---|
| id | CHAR(32) | False | PK  |
| user_id | CHAR(32) | False | users.id |
| token_hash | VARCHAR(64) | False |  |
| expires_at | DATETIME | False |  |
| last_seen_at | DATETIME | True |  |
| revoked_at | DATETIME | True |  |
| created_at | DATETIME | False |  |

### projects

| Column | Type | Nullable | Key / reference |
|---|---|---|---|
| id | CHAR(32) | False | PK  |
| user_id | CHAR(32) | False | users.id |
| name | VARCHAR(120) | False |  |
| source_type | VARCHAR(20) | False |  |
| repository | VARCHAR(255) | True |  |
| default_branch | VARCHAR(120) | False |  |
| template | VARCHAR(40) | True |  |
| created_at | DATETIME | False |  |

### workspaces

| Column | Type | Nullable | Key / reference |
|---|---|---|---|
| id | CHAR(32) | False | PK  |
| project_id | CHAR(32) | False | projects.id |
| user_id | CHAR(32) | False | users.id |
| status | VARCHAR(30) | False |  |
| base_commit_sha | VARCHAR(64) | True |  |
| created_at | DATETIME | False |  |
| last_activity_at | DATETIME | False |  |

### workspace_sessions

| Column | Type | Nullable | Key / reference |
|---|---|---|---|
| id | CHAR(32) | False | PK  |
| workspace_id | CHAR(32) | False | workspaces.id |
| user_id | CHAR(32) | False | users.id |
| opencode_session_id | VARCHAR(120) | False |  |
| title | VARCHAR(120) | False |  |
| status | VARCHAR(30) | False |  |
| created_at | DATETIME | False |  |

### execution_events

| Column | Type | Nullable | Key / reference |
|---|---|---|---|
| id | INTEGER | False | PK  |
| session_id | CHAR(32) | False | workspace_sessions.id |
| kind | VARCHAR(50) | False |  |
| data | TEXT | False |  |
| created_at | DATETIME | False |  |

## Ownership and storage

Project is the logical record; Workspace owns one filesystem checkout; WorkspaceSession binds a conversation to that same checkout. Each has user_id and server-owned UUID. Runtime path is derived as `{WORKSPACE_ROOT}/{user_id}/{workspace_id}/repo`; it is neither client input nor an API field. Base SHA remains null for blank/template origins. A default `work` branch is created locally.

Execution events store ordered IDs and sanitized lifecycle metadata; they do not copy source files or complete model responses. Runtime conversation files remain under the per-workspace runtime directory. PostgreSQL transaction success does not make filesystem creation transactional: failed setup preserves a failed workspace record/files for recovery. No automatic delete cascade/cleanup policy is implemented.

Missing target tables: GitHub installations/connections, encrypted credentials, upload metadata, task leases/idempotency, billing profiles/plans/versions/subscriptions/payments/ledger and audit trails. Add schema with the corresponding implementation, not empty tables suggesting completion.


## Codex merge, 2026-10-05

Account management, recovery, audit, locations, encrypted payment methods and user-authorized GitHub integration were merged while preserving subscriptions and project archiving. See [MERGE_REPORT.md](MERGE_REPORT.md) and [Codex reference](reference/codex/DATABASE_REFERENCE.md). New migration: `0006_account_management`. External integrations still require configuration; no production connection or deployment was tested.
