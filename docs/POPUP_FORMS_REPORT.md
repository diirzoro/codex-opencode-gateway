# Centered popup forms — 2026-10-05

Local workspace: `D:\opencodde agent\codex project\project`. No deployment, SSH or push.

The screenshot showed full-width account rows and an always-visible suspension form. Account summaries now have a bounded centered width, while actions open on demand in native dialogs. Forms have a maximum width of 600px, vertically grouped labeled fields, a shared Save/Cancel action row, an accessible close button, a soft backdrop and responsive height with scrolling when needed. Native dialogs provide keyboard focus containment and Escape dismissal. Unsaved password values clear when dialogs close.

## Reviewed entry points

| Area | Current presentation |
| --- | --- |
| Customer/admin account profile | Centered information summary; phone/postal editing in one popup |
| Password change | Popup with current/new password fields |
| Suspend/delete request | Popup with username, password and action choice; separate styled confirmation |
| Password recovery/reset | Popup; existing recovery APIs unchanged |
| Login/registration | Centered popup using the existing authentication handlers |
| Platform payment methods | Add/edit popup, conditional bank/wallet fields, existing scoped CRUD |
| Customer checkout | Existing centered plan/method/transfer popup retained; no admin editor exposed |
| Administrative receipt review | Styled reference popup instead of browser prompt |
| Plans | Add popup; existing edit/detail popups converted to native dialogs |
| AI/runtime policy | Edit popup with existing policy fields and save API |
| Provider credentials | Workspace provider credential/authorization entry forms use the shared popup helper |
| Countries/regions/cities | Add/edit popup; existing parent/type selection and list remain page controls |
| User/role administration | Native user edit/detail dialogs and role selection popup |
| Project creation/rename | Creation popup and rename popup |
| Repository/branch selection | Existing bounded repository popup retained |
| Commit message | Styled input popup instead of browser prompt |
| Destructive confirmations | Styled native popup instead of browser confirm |

Conversation composers, list search/filter fields and workspace/provider/model selectors remain where they are used. These are ongoing interaction controls, rather than permanently exposed create/edit forms.

## Verification

Eight headed Chromium tests passed together after the final modal changes. They cover real profile persistence, a real admin policy save, receipt review/subscription activation, customer/admin separation, account cancellation without suspension, password clearing, Escape, first-field focus, bounded and centered dialog widths, mobile overflow, Arabic RTL, workspace creation, and customer/admin/owner navigation. Native prompt/confirm calls were removed from the four application scripts. JavaScript syntax checks passed for all four scripts.

Visual evidence inspected: `profile-popup.png`, `account-action-mobile.png` and `security-popup-ar.png` under `D:\opencodde agent\codex project\.audit\workspace-first-evidence`.

Files changed in this phase: `app.js`, `management.js`, `enhancements.js`, `dashboards.js`, `index.html`, browser tests and documentation. Payment list rendering now discards stale concurrent results to prevent duplicate receipt buttons. No backend API, schema or migration changed in this phase. Live provider authorization, automatic online payments and production acceptance are not established by these UI tests.
