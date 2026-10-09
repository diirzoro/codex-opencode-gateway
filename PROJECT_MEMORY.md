# OpenCode Gateway — Project Memory

Updated: 2026-10-09
Branch policy: development on `updates`; production on `master`. Do not merge or deploy without explicit approval.

## Architecture baseline
- Browser -> Nginx -> FastAPI Gateway -> PostgreSQL / workspace-specific OpenCode runtime.
- Gateway uses the existing internal production binding; workspace OpenCode processes use dynamic loopback ports.
- Browser never talks directly to OpenCode.
- OpenCode is the source of truth for provider/model/agent catalogs and supported capabilities.
- GitHub is the permanent source for GitHub-backed projects; Gateway worktrees are temporary.
- Credentials remain encrypted server-side.
- Production `.env`, PostgreSQL, encryption keys, PayPal/GitHub secrets, runtime and workspace data are protected operational state.

## Completed phases
### Phase 1
Core Gateway/workspace/runtime architecture, backend/frontend integration and project/workspace/session foundations.

### Phase 2
Runtime restoration, caching, workspace recovery and reduced unnecessary discovery work.

### Phase 3
Provider/model/agent discovery and selection, curated provider behavior, lazy model discovery and runtime snapshot/cache improvements.

### Phase 4
Session lifecycle, idempotent submissions, stop/cancel, archive/restore/history, review panels and durable provider connect/disconnect/reconnect behavior.

### Provider stabilization
Correct OpenCode auth methods, credential validation, auth refresh, inline modal feedback and reconnect/disconnect behavior.

### Phase 5-1
Workspace UX and security hardening:
- simplified conversation/composer flow
- safe tool/activity presentation
- 15-minute server-authoritative idle login timeout
- explicit meaningful-activity acknowledgement
- sensitive browser state cleanup on logout/expiry

### Phase 5-2
GitHub workflow, trials and entitlements:
- GitHub App repository/branch workflow
- shallow working copies and optional sparse checkout
- explicit commit/push and FF-only sync
- local project limit 50 MB
- GitHub working-copy limit 512 MiB
- Core trial 30 days
- Advanced trial 10 days from first actual advanced use
- server-side entitlement enforcement
- Google/GitHub sign-in identities
- composer attachments and improved dialog/form UX

## Billing and renewal
- Renewal base: `max(now, current_period_end)`.
- Purchased duration stacks on remaining paid time.
- Trial time is not added to paid renewal time.
- Selecting a renewal plan does not erase current paid access.
- Payment activation is guarded against replay/double-counting and concurrent renewal races.
- Dashboard and Workspace counters use the same server entitlement truth.

## Retention policies
### Account/customer
- Expired access freezes coding/execution.
- Customer account retention: 90 days after access expiry.
- After that period the customer becomes archived/inactive rather than losing the customer relationship.
- Preserved: identity/contact relationship, billing history and explicit marketing-consent history.
- Removed on archival: operational sessions, provider credentials, GitHub authorization and runtime secrets/state.
- Reactivation: archived -> verified email -> limited renewal-only session -> verified real payment -> fresh password -> normal login.
- Social sign-in cannot bypass archived-account reactivation.

### Workspace/project files
- Local project files: cleanup after 7 days of meaningful inactivity; warning from about day 5.
- GitHub temporary worktree: cleanup after 73 hours of meaningful inactivity.
- Original GitHub repository is never deleted or altered by Gateway retention cleanup.
- Passive polling does not extend retention.
- Cleanup is blocked while execution/upload/write activity is in progress.
- Existing files receive an initial grace period when retention is first activated.

### Marketing
- Marketing consent defaults to not granted.
- Consent/opt-out and permitted channels are explicit.
- Contact information is not automatic advertising consent.

## Repository cleanup
- Obsolete `reference/original-prototype/` content was removed.
- Dead `config.js` frontend configuration was removed after verifying the live frontend does not reference it.
- Dead `/assets/yemen-hero.svg` and `/config.js` public routes were removed.
- Broken references to the removed `docs/` tree were replaced with the maintained root/deployment references.
- Release packaging now validates the current project memory, improvement plan and migration head instead of deleted documentation.

## Current branch state
- `master` includes the reviewed Phase 5-2, hotfix, retention/reactivation and documentation work through merge commit `96255d79a39e7c336ea7c7b56fdbb7df7b03ac83`.
- `updates` was synchronized to that merge before the current cleanup work.
- Cleanup/performance work continues on `updates` first.

## Deployment cautions
Before production deployment, run Alembic normally through `head`. Current migration head is:
- `0012_advanced_trial.py`
- `0013_login_identity.py`
Never run later migrations selectively ahead of predecessors.
