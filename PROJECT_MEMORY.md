# OpenCode Gateway — Project Memory

Updated: 2026-10-09
Branch policy: development on `updates`; production on `master`. Do not merge or deploy without explicit approval.

## Architecture baseline
- Browser -> Nginx -> FastAPI Gateway -> PostgreSQL / workspace-specific OpenCode runtime.
- Gateway listens on the existing internal production binding; workspace OpenCode processes use dynamic loopback ports.
- Browser never talks directly to OpenCode.
- OpenCode is the source of truth for provider/model/agent catalogs and supported capabilities.
- GitHub is the permanent source for GitHub-backed projects; Gateway worktrees are temporary.
- Credentials remain encrypted server-side. Production secrets, PayPal configuration, GitHub App secrets and runtime data are protected operational areas.

## Completed phases
### Phase 1
Established the core Gateway/workspace/runtime architecture, backend/frontend integration and stable project/workspace/session foundations.

### Phase 2
Improved runtime restoration, caching and workspace state recovery. Reduced unnecessary discovery work and improved startup behavior.

### Phase 3
Improved provider/model/agent discovery and selection, provider catalog/search behavior, lazy model discovery and runtime snapshot/caching.

### Phase 4
Completed session lifecycle and provider durability work: session state, stop/cancel, archive/restore/history, review panels and durable provider connect/disconnect/reconnect behavior.

### Provider stabilization after Phase 4
Corrected OpenCode provider authentication methods, credential validation, auth refresh, modal feedback and reconnect/disconnect behavior.

### Phase 5-1
Workspace UX and security hardening:
- simplified conversation/composer workflow
- safe tool/activity presentation
- 15-minute server-authoritative idle login timeout
- explicit activity acknowledgement
- sensitive browser state cleanup on logout/expiry

### Phase 5-2
GitHub workflow, trials and entitlements:
- GitHub App based repository/branch workflow
- shallow working copies and optional sparse checkout
- explicit commit/push and FF-only sync
- local project limit 50 MB
- GitHub working-copy limit 512 MiB
- Core trial 30 days
- Advanced trial 10 days from first actual advanced use
- server-side entitlement enforcement
- migrations 0012 and 0013 are pending on production until deployment

### Hotfix pack
- shared draggable desktop dialogs and lighter backdrop
- browser password-manager semantics and remember-identity only
- Google/GitHub sign-in with state/PKCE and verified identity
- composer attachments with refresh/edit/regenerate preservation
- sparse checkout support without changing Git source-of-truth policy

## Billing and renewal
- Paid renewal base is `max(now, current_period_end)`.
- Purchased duration is added to remaining paid time.
- Trial time is not added to paid renewal time.
- Plan selection does not erase already purchased access.
- Payment activation is protected against duplicate/replayed activation and concurrent renewal races.
- Dashboard and Workspace remaining-time displays use the existing server entitlement payload.

## Retention policies
### Account/customer
- Expired access freezes execution/coding rather than immediately deleting the account.
- Account/customer retention period: 90 days after access expiry.
- After the retention period the customer becomes archived/inactive rather than losing the customer relationship.
- Preserved: identity/contact relationship, billing history and explicit marketing-consent history.
- Removed on archival: operational secrets, sessions, provider credentials, GitHub authorization and runtime state.
- Archived-customer reactivation flow:
  archived -> verified email ownership -> limited renewal-only session -> verified real payment -> fresh password -> normal login.
- Social sign-in cannot bypass archived-account reactivation.

### Workspace/project files
- Local project files: cleanup after 7 days of meaningful inactivity; warning from about day 5.
- GitHub temporary worktree: cleanup after 73 hours of meaningful inactivity.
- Original GitHub repository is never deleted or altered by retention cleanup.
- Passive polling does not extend retention.
- Cleanup is blocked while execution/upload/write activity is in progress.
- Existing data receives an initial grace period when the retention policy is first activated.

### Marketing
- Marketing consent defaults to not granted.
- Consent/opt-out and permitted channels are explicit.
- Customer contact data must not be treated as automatic advertising consent.

## Current branch state
At the time this memory was updated:
- `master`: production baseline at `f19f007487125cc4402695c55941c4734dab2293`.
- `updates` includes the Phase 5-2, hotfix, retention/renewal and archived-reactivation work through `ff55fcb6e56a5a706adf3520faa03c419f950fd6`.
- No merge or deployment has been performed for these updates.

## Deployment cautions
Before a future production deployment, apply Alembic migrations in normal order through head; at minimum the current updates branch contains:
- `0012_advanced_trial.py`
- `0013_login_identity.py`
Do not run later migrations selectively ahead of their predecessors.
