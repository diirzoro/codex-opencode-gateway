# Implementation status — requirements v2.1

Updated 2026-10-03. Local development only; no VPS connection, upload or deployment in this phase. Development deliverable: `D:/opencodde agent/opencode project`.

Source: `OpenCode_Platform_Requirements_AR_v2_1.md`, SHA256 `4282c6e8d960f6d0f0f80a509c32cc7affaa3e1d3f05fd75e75c123d8c55b551`. Its 224 textual requirement/policy/acceptance/decision entries are retained below. Blank sections are not silently filled with assumptions. The pasted user request supplements route/table expectations; subsequent user directions authorize local development and the ChatGPT/Kimi-inspired design with recognizable SVG icons.

## Definitions

- REAL: connected backend/runtime behavior with scoped local evidence.
- PARTIAL: implemented portion, with specific omissions or incomplete verification.
- SIMULATED: intentionally synthetic product behavior. None is presented as operational in this delivered UI. Mocks in boundary tests are test doubles, not product features.
- MISSING: no complete implementation of the requested feature.
- BLOCKED: external prerequisite, unresolved decision, or verification prohibited by current scope.

## Current real system

Accounts, opaque hashed cookie sessions, required fields/location lookup, startup guards and admin/owner authorization are connected. Blank and three starter templates create actual owned directories and Git repositories. Files/diff/commit use the filesystem and Git. New Session creates a real OpenCode session on existing files in opt-in local mode. User metrics come from DB. Public assets are explicitly allowlisted.

The frontend has a neutral conversation-focused layout, official OpenCode SVG paths, GitHub mark, line icons, Arabic/English and dark/light modes. Disabled integrations have honest empty states. No fake chat response, test success, remote push, billing date, price or payment history is generated.

## Baseline audit and fixes

Initial audit found root-wide static serving exposed backend source and `.env.example`; mixed-case username login failed; null profile fields could cause 500; owner was denied admin access; frontend contained sample operational data. These were fixed. A newer local admin overview implementation and its test were discovered and preserved during final merge. Existing device-local draft storage is left untouched; it is not imported as server-backed workspaces.

## Verification boundary

See PHASE_REPORT.md for exact test results and changed files. Python 3.13 local SQLite tests and an actual OpenCode 1.18.31 two-session smoke test passed. Alembic upgrade to 0002 succeeded on a fresh SQLite database; PostgreSQL dialect SQL generation succeeded, but PostgreSQL 16 execution and target Python 3.12 remain unverified. Browser tests use a separate loopback test database.

Missing: GitHub App authentication/clone/private repo/revoke/publish/push verification, provider authentication and encrypted secret lifecycle, full agent tool-event bridge, quotas, OS/network sandbox, previews/uploads/retention and billing. The message/approval/SSE adapters are PARTIAL until a real authenticated provider workflow is exercised. Local runtimes use separate directories/processes, not a public multi-tenant security boundary.

## Requirement traceability

Read this status, API_REFERENCE.md and ARCHITECTURE.md before changing behavior. Update evidence/status/API/schema/security/roadmap after each phase. Counts include repeated acceptance criteria and policies; they are not a completion percentage.

Counts: REAL=21, PARTIAL=96, SIMULATED=0, MISSING=93, BLOCKED=14.

### R01.01 — section 1, source line 71

- **Requirement:** الهدف هو تمكين المستخدم من العمل على مشروع GitHub من الهاتف أو الكمبيوتر عبر المتصفح، بدون تثبيت بيئة تطوير محلية وبدون رفع مشروعه إلى خادم المنصة كنسخة دائمة. GitHub يبقى المصدر الدائم للكود، بينما تستخدم المنصة مساحة عمل مؤقتة لتشغيل OpenCode وقراءة الملفات وتعديلها واختبارها ومراجعتها.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R02.01 — section 2, source line 85

- **Requirement:** ملاحظة تشغيلية: ظهور No folders found في واجهة OpenCode الحالية متوقع لأن OpenCode معزول عن /home ولم يُنشئ Gateway بعد Workspace فعليًا. الحل المعتمد هو أن ينشئ Workspace Manager المساحة والملفات أولًا ثم يربط OpenCode بها، وليس إعادة فتح ملفات الخادم.
- **Status:** BLOCKED
- **Phase:** MVP / phased
- **Evidence / files / tests:** Production state intentionally not inspected under local-only instruction. Local workspace creation works.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Review production only after explicit authorization; this does not block local development.

### R03.01 — section 3, source line 89

- **Requirement:** GitHub هو المصدر الدائم للكود؛ لا يُخزن source code في PostgreSQL ولا يُنسخ إلى مستودع مالك المنصة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Nine application tables; no repository content or raw tokens in metadata DB; schema generated below.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Only implemented phase tables exist. Runtime stores conversation/content locally; later retention and secret policies required.

### R03.02 — section 3, source line 91

- **Requirement:** كل جلسة عمل تحتاج Workspace على filesystem مؤقت، مع ownership واضح ومعرّف مستخدم ومعرّف جلسة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R03.03 — section 3, source line 93

- **Requirement:** OpenCode يعمل على ملفات Workspace الحقيقية وليس على GitHub مباشرة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R03.04 — section 3, source line 95

- **Requirement:** الـGateway هو نقطة الدخول الوحيدة للمستخدم؛ OpenCode نفسه يصبح خدمة داخلية قبل الإطلاق العام.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py binds per-workspace local process with separate HOME/XDG, Basic auth and directory; owned route lookup.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Trusted local development only; no OS/network isolation, quotas, durable task recovery or retention. Health/status are auth-scoped global diagnostics, not workspace calls.

### R03.05 — section 3, source line 97

- **Requirement:** عند نجاح Push والتحقق من commit البعيد يمكن تنظيف Workspace حسب سياسة الاحتفاظ.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R03.06 — section 3, source line 99

- **Requirement:** كل العمليات الحساسة — GitHub tokens، AI credentials، session ownership، workspace paths — تُحسم في الخادم وليس في المتصفح.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Nine application tables; no repository content or raw tokens in metadata DB; schema generated below.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Only implemented phase tables exist. Runtime stores conversation/content locally; later retention and secret policies required.

### R04.01 — section 4.2, source line 109

- **Requirement:** لا Redis، لا Kubernetes، لا microservices متعددة، ولا queue منفصلة ما لم تظهر حاجة تشغيلية حقيقية. يبدأ المنتج بخدمة Gateway واحدة + PostgreSQL + OpenCode + Workspace Manager، ثم نفصل المهام الطويلة لاحقًا عند الحاجة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Architecture policy retained; see ARCHITECTURE.md and SECURITY_MODEL.md.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Policy statements are not evidence that all future runtime/payment enforcement is implemented.

### R05.01 — section 5, source line 119

- **Requirement:** مصادقة مزود AI أوسع من API Key: دعم API key أو OAuth / device-code / login عندما يدعمه OpenCode أو المزود، وعدم افتراض أن كل المزودات تعمل بمفتاح فقط.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R05.02 — section 5, source line 121

- **Requirement:** OpenCode Context منفصل لكل مستخدم/Workspace: عدم مشاركة HOME/config/data/state/cache أو auth بين المستخدمين. كل Workspace يمتلك سياق تشغيل مستقل أو معزول.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R05.03 — section 5, source line 123

- **Requirement:** منع الهروب من جذر Workspace: File browser وOpenCode لا يعرضان ملفات الخادم. منع ../ والمسارات المطلقة وsymlink escape والوصول إلى /home و/etc وأسرار المضيف.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R05.04 — section 5, source line 125

- **Requirement:** رفع ملفات وصور إلى المشروع: رفع آمن داخل Workspace مع حدود حجم ونوع، اسم تخزين مولد، metadata في PostgreSQL وحذف الملف مع Workspace.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R05.05 — section 5, source line 127

- **Requirement:** دورة حياة GitHub credentials: GitHub App، installation id، short-lived tokens، إلغاء الربط، webhooks عند سحب الوصول، وعدم تخزين tokens في المتصفح.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R05.06 — section 5, source line 129

- **Requirement:** سياسة الفروع: الافتراضي: work branch → review → commit → push → PR اختياري. لا force-push أو merge تلقائي إلى main.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R05.07 — section 5, source line 131

- **Requirement:** حالات Agent حقيقية: Reading, Analyzing, Editing, Running command, Running tests, Waiting approval, Failed, Completed محفوظة في backend.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R05.08 — section 5, source line 133

- **Requirement:** الاستئناف بعد انقطاع الاتصال: SSE/WebSocket بأرقام أحداث أو sequence IDs حتى يعاد الاتصال دون تكرار المهمة أو الفوترة.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R05.09 — section 5, source line 135

- **Requirement:** حدود الموارد: CPU/RAM/disk/runtime/concurrency limits حسب الباقة، مع timeout واضح وقتل آمن للعمليات المعلقة.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R05.10 — section 5, source line 137

- **Requirement:** PostgreSQL للـmetadata فقط: المستخدمون والجلسات والمحادثات والفوترة والـmetadata في DB؛ source code والملفات التنفيذية خارج PostgreSQL.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Nine application tables; no repository content or raw tokens in metadata DB; schema generated below.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Only implemented phase tables exist. Runtime stores conversation/content locally; later retention and secret policies required.

### R05.11 — section 5, source line 139

- **Requirement:** تصنيف المتطلبات حسب المرحلة: كل ميزة توسم MVP Required أو Phase 2 أو Future/Optional لمنع توسع غير منضبط.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Architecture policy retained; see ARCHITECTURE.md and SECURITY_MODEL.md.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Policy statements are not evidence that all future runtime/payment enforcement is implemented.

### R05.12 — section 5, source line 141

- **Requirement:** Non-goals للنسخة الأولى: لا دعم لكل أنواع المشاريع، لا تعاون جماعي حي، لا قواعد إنتاج تلقائية، لا حفظ دائم للكود، ولا وعد بمزودات مجانية دائمة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Architecture policy retained; see ARCHITECTURE.md and SECURITY_MODEL.md.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Policy statements are not evidence that all future runtime/payment enforcement is implemented.

### R05.13 — section 5, source line 143

- **Requirement:** منع الإحصائيات الوهمية: لا تعرض لوحة الإدارة أرقامًا hardcoded كحقيقة؛ إما query حقيقي أو Not available yet/Preview.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual DB user aggregates. No invented payments, visitor or resource counters in active UI.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement audited metrics/operations only when real sources exist.

### R05.14 — section 5, source line 145

- **Requirement:** Owner/Admin bootstrap وأدوار واضحة: Owner، Admin، Support، Finance، User، مع أقل صلاحية لازمة وسجل تدقيق، وإنشاء أول Owner بطريقة موثوقة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Server admin/owner authorization, real user list and overview counts retained.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Support/finance roles, audited owner bootstrap, admin mutations/export remain missing.

### R05.15 — section 5, source line 147

- **Requirement:** OpenCode داخلي فقط قبل الإطلاق: لا وصول عام مباشر إلى 4096؛ كل طلب يمر عبر Gateway بعد التحقق من الهوية والملكية.
- **Status:** BLOCKED
- **Phase:** MVP / phased
- **Evidence / files / tests:** No public deployment is authorized.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resource/billing limits require policy decisions and target capacity before public launch.

### R05.16 — section 5, source line 149

- **Requirement:** شروط قبول قابلة للاختبار: نجاح المنتج يقاس باختبارات end-to-end: مستخدم → GitHub → Workspace → OpenCode حقيقي → Diff → Push صحيح → Cleanup آمن.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R06.01 — section 6.1, source line 155

- **Requirement:** هوية OpenCode Gateway مستقلة مع توضيح أن OpenCode وGitHub خدمات خارجية وليست علاقة رسمية بالمنصة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** index.html/styles.css/app.js; desktop/mobile Playwright, Arabic/English, light/dark, real SVG brand marks.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Working responsive workspace layout. Public legal/support content, full admin localization and some accessibility refinements remain.

### R06.02 — section 6.1, source line 157

- **Requirement:** شرح المسار الكامل بصريًا، الباقات عند اعتمادها، تجربة مجانية 10 أيام، FAQ، الخصوصية، الشروط، الدعم، العربية/الإنجليزية، RTL/LTR، Light/Dark، Responsive.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** index.html/styles.css/app.js; desktop/mobile Playwright, Arabic/English, light/dark, real SVG brand marks.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Working responsive workspace layout. Public legal/support content, full admin localization and some accessibility refinements remain.

### R06.03 — section 6.1, source line 159

- **Requirement:** التصفح العام متاح للزائر، لكن Workspace/Account/Admin/Onboarding المحمي يتطلب session حقيقية.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Auth and profile APIs wired to frontend; case-insensitive login, null validation and owner/admin access fixed.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Password reset, verification, rate limiting and expanded roles remain absent.

### R06.04 — section 6.2, source line 163

- **Requirement:** الحقول: username، email، password، phone، country، postal/ZIP، region/city اختياريان.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Auth routes, schemas/account.py, app.js; security/account tests and browser authentication flow.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Registration, cookie sessions and startup guards verified locally; no production claim.

### R06.05 — section 6.2, source line 165

- **Requirement:** الدخول بالبريد أو username وكلمة المرور. Google/GitHub login يضافان فقط بعد تكامل حقيقي.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Auth and profile APIs wired to frontend; case-insensitive login, null validation and owner/admin access fixed.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Password reset, verification, rate limiting and expanded roles remain absent.

### R06.06 — section 6.2, source line 167

- **Requirement:** الجلسة opaque random token، يخزن hash فقط في PostgreSQL، Cookie HttpOnly + SameSite=Strict، وSecure=true عند HTTPS.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Auth routes, schemas/account.py, app.js; security/account tests and browser authentication flow.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Registration, cookie sessions and startup guards verified locally; no production claim.

### R06.07 — section 6.2, source line 169

- **Requirement:** الـfrontend عند التحميل يستدعي GET /api/auth/me، ولا يعتمد على إخفاء الأزرار فقط.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Auth routes, schemas/account.py, app.js; security/account tests and browser authentication flow.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Registration, cookie sessions and startup guards verified locally; no production claim.

### R06.08 — section 6.2, source line 171

- **Requirement:** Admin يحتاج session + role=admin/owner على الخادم؛ غير المصرح له لا يرى البيانات حتى لو فتح رابط الصفحة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Server admin/owner authorization, real user list and overview counts retained.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Support/finance roles, audited owner bootstrap, admin mutations/export remain missing.

### R07.01 — section 7, source line 175

- **Requirement:** استخدام GitHub App أفضل من PAT عام، بصلاحيات repositories المختارة فقط.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R07.02 — section 7, source line 177

- **Requirement:** حفظ installation id وrepository identifiers والـmetadata في PostgreSQL، وليس raw token الدائم.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R07.03 — section 7, source line 179

- **Requirement:** استخراج short-lived installation token وقت الحاجة واستخدامه server-side فقط.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R07.04 — section 7, source line 181

- **Requirement:** عرض repos/branches المسموحة من API حقيقي؛ لا hardcoded project/branch في الواجهة.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R07.05 — section 7, source line 183

- **Requirement:** دعم private repositories ضمن الصلاحيات الممنوحة.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R07.06 — section 7, source line 185

- **Requirement:** عند revoke/uninstall webhook تُعلّم connection كمنتهية وتُوقف أي عملية جديدة وتتعامل بأمان مع Workspace مفتوح.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R07.07 — section 7, source line 187

- **Requirement:** لا يرسل token للمتصفح ولا إلى OpenCode logs أو agent prompt.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R08.01 — section 8, source line 191

- **Requirement:** الفصل بين Provider وModel وAgent mode.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/providers.py reads installed runtime /provider and /provider/auth. Frontend provider/model controls use response.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Provider credential setup/auth flows and agent mode selection missing; no connected paid model tested.

### R08.02 — section 8, source line 193

- **Requirement:** تحميل قائمة providers/models من نسخة OpenCode المستخدمة أو API موثوق، لا قائمة ثابتة طويلة في frontend.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/providers.py reads installed runtime /provider and /provider/auth. Frontend provider/model controls use response.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Provider credential setup/auth flows and agent mode selection missing; no connected paid model tested.

### R08.03 — section 8, source line 195

- **Requirement:** دعم API key أو OAuth/device-code/اشتراك عندما يدعمه المزود/OpenCode.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R08.04 — section 8, source line 197

- **Requirement:** عند تخزين credential: تشفير server-side بمفتاح خارج قاعدة البيانات؛ إظهار آخر أحرف فقط؛ عدم إعادته كاملًا للواجهة.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R08.05 — section 8, source line 199

- **Requirement:** يمكن خيار session-only credential للعميل الذي لا يريد الحفظ.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R08.06 — section 8, source line 201

- **Requirement:** اختبار credential من الخادم دون إدخاله في logs.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R08.07 — section 8, source line 203

- **Requirement:** المجاني يظهر فقط إذا كان متاحًا فعليًا ولا يوصف بأنه ضمان دائم.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Architecture policy retained; see ARCHITECTURE.md and SECURITY_MODEL.md.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Policy statements are not evidence that all future runtime/payment enforcement is implemented.

### R08.08 — section 8, source line 205

- **Requirement:** فاتورة المنصة منفصلة عن فاتورة مزود AI؛ BYOK لا يعني أن المنصة تتحمل تكلفة API.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Architecture policy retained; see ARCHITECTURE.md and SECURITY_MODEL.md.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Policy statements are not evidence that all future runtime/payment enforcement is implemented.

### R09.01 — section 9, source line 209

- **Requirement:** التخطيط المعتمد: sidebar للجلسات/المشاريع، الوسط للمحادثة والAgent، panel للمراجعة Files/Diff/Logs. على الهاتف تصبح Agent-first مع drawers/tabs بدل تصغير سطح المكتب.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** index.html/styles.css/app.js; desktop/mobile Playwright, Arabic/English, light/dark, real SVG brand marks.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Working responsive workspace layout. Public legal/support content, full admin localization and some accessibility refinements remain.

### R09.02 — section 9, source line 211

- **Requirement:** إنشاء Workspace بعد تحقق الحساب والاشتراك وGitHub permission.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.03 — section 9, source line 213

- **Requirement:** المسار المقترح: /var/lib/opencode-workspaces/{user_id}/{workspace_id}/repo
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.04 — section 9, source line 215

- **Requirement:** نسخ الفرع المحدد shallow/partial clone عندما يناسب، مع التعامل مع LFS/submodules بوضوح.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R09.05 — section 9, source line 217

- **Requirement:** عرض اسم repo والbranch وbase commit SHA للمستخدم.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.06 — section 9, source line 219

- **Requirement:** File browser حقيقي مرتبط بالWorkspace فقط، ويعرض modified/added/deleted وdiff counts.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.07 — section 9, source line 221

- **Requirement:** لا تغيير branch مع تعديلات معلقة إلا بعد commit/stash/discard بقرار واضح.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R09.08 — section 9, source line 223

- **Requirement:** الأوامر الحساسة تحتاج approval داخل المحادثة قبل التنفيذ.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R09.09 — section 9.1, source line 227

- **Requirement:** عند إنشاء Workspace جديد يجب أن يختار المستخدم أحد مصادر البداية التالية: GitHub Repository، Blank Project من الصفر، أو Template مدعوم مثل HTML/CSS/JS أو Python أو Node.js. لا يُجبر المستخدم على امتلاك repository جاهز قبل بدء العمل.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.10 — section 9.1, source line 229

- **Requirement:** GitHub Repository: يختار المستخدم repository وbranch مصرحًا بهما، ثم ينسخ Workspace Manager الفرع إلى مساحة مؤقتة مملوكة للمستخدم.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R09.11 — section 9.1, source line 231

- **Requirement:** Blank Project: ينشئ Workspace Manager مجلد repo فارغًا داخل مساحة المستخدم، ويهيئ Git محليًا عند الحاجة، ويمكن إضافة README/.gitignore ابتدائيين دون فرض هيكل مشروع.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/workspaces.py, routes/workspaces.py; test_workspaces.py and browser flow exercise actual files, Git diff and commit.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/HTML/Python/Node templates verified. No remote push claim.

### R09.12 — section 9.1, source line 233

- **Requirement:** Template: ينشئ النظام ملفات بداية محدودة ومعروفة للـstack المختار، مع توضيح أن القالب نقطة بداية وليس بيئة إنتاج كاملة.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/workspaces.py, routes/workspaces.py; test_workspaces.py and browser flow exercise actual files, Git diff and commit.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/HTML/Python/Node templates verified. No remote push claim.

### R09.13 — section 9.1, source line 235

- **Requirement:** يمكن للمشروع الجديد أن يبقى مؤقتًا أثناء العمل، ثم يُنشر لاحقًا إلى GitHub. إذا لم يملك التكامل صلاحية إنشاء repository جديد، يطلب النظام من المستخدم إنشاء/اختيار repository ثم ينفذ Push إليه.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R09.14 — section 9.2, source line 239

- **Requirement:** Project: الكيان المنطقي الذي يراه المستخدم، وقد يكون مصدره GitHub أو Blank أو Template. يحتفظ بالاسم والمصدر والمرجع إلى GitHub عند توفره.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.15 — section 9.2, source line 241

- **Requirement:** Workspace: نسخة filesystem مؤقتة ومعزولة لمشروع واحد، لها owner واضح ومسار داخلي لا يُكشف للمتصفح.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.16 — section 9.2, source line 243

- **Requirement:** OpenCode Session: محادثة/تنفيذ Agent يعمل على Workspace موجود. إنشاء New Session لا ينشئ مشروعًا جديدًا ولا ينسخ الملفات من جديد؛ بل يبدأ جلسة جديدة على نفس ملفات المشروع.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py; test_real_opencode_new_session_retains_files starts installed OpenCode 1.18.31 and creates two distinct runtime sessions on one workspace.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Requires OPENCODE_RUNTIME_MODE=local. Provider-backed edits are not covered by this test.

### R09.17 — section 9.2, source line 245

- **Requirement:** يمكن لـWorkspace واحد أن يحتوي عدة Sessions متتابعة مثل: بناء النسخة الأولى، إضافة Login، إصلاح الهاتف. كل Session ترى الحالة الحالية لنفس الملفات ما لم ينشئ المستخدم Workspace جديدًا.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py; test_real_opencode_new_session_retains_files starts installed OpenCode 1.18.31 and creates two distinct runtime sessions on one workspace.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Requires OPENCODE_RUNTIME_MODE=local. Provider-backed edits are not covered by this test.

### R09.18 — section 9.3, source line 249

- **Requirement:** OpenCode لا يجب أن يبحث عشوائيًا داخل خادم VPS ولا أن يعرض مجلدات النظام. Gateway/Workspace Manager هو المسؤول عن إنشاء المسار الصحيح ثم تشغيل أو ربط OpenCode بذلك Workspace فقط.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.19 — section 9.3, source line 251

- **Requirement:** المسار المستهدف يبقى مثل: /var/lib/opencode-workspaces/{user_id}/{workspace_id}/repo، ويُنشأ قبل إنشاء Session. إذا كان المجلد فارغًا فهذه حالة Blank Project صحيحة، وليست خطأ No folders found.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.20 — section 9.3, source line 253

- **Requirement:** واجهة Gateway تعرض اسم المشروع والمصدر والbranch إن وجد، ولا تعرض المسار الحقيقي على Linux. الوصول إلى Files/Diff/Logs يأتي من Workspace الحقيقي عبر backend.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.21 — section 9.4, source line 257

- **Requirement:** New Project → اختيار GitHub/Blank/Template → إنشاء Workspace → تجهيز الملفات → ربط OpenCode بالمسار → إنشاء أول Session → بدء Agent.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R09.22 — section 9.4, source line 259

- **Requirement:** New Session → اختيار Project/Workspace موجود → إنشاء OpenCode Session جديدة → متابعة العمل على نفس الملفات دون إنشاء Workspace آخر.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py; test_real_opencode_new_session_retains_files starts installed OpenCode 1.18.31 and creates two distinct runtime sessions on one workspace.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Requires OPENCODE_RUNTIME_MODE=local. Provider-backed edits are not covered by this test.

### R10.01 — section 10, source line 263

- **Requirement:** Gateway لا يفتح واجهة OpenCode العامة للمستخدم كبديل للمنتج. بل يستدعي OpenCode API/Server من backend ويوجه الجلسة إلى Workspace المملوك للمستخدم.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py binds per-workspace local process with separate HOME/XDG, Basic auth and directory; owned route lookup.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Trusted local development only; no OS/network isolation, quotas, durable task recovery or retention. Health/status are auth-scoped global diagnostics, not workspace calls.

### R10.02 — section 10, source line 265

- **Requirement:** إضافة OPENCODE_URL داخليًا مثل http://127.0.0.1:4096 في بيئة التطوير.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Internal OPENCODE_URL, authenticated health/status, frontend session state; actual local /global/health and /doc inspected.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Runtime 1.18.31 only. Browser uses Gateway APIs; shared 4096 process is health-only. Public network exposure not assessed.

### R10.03 — section 10, source line 267

- **Requirement:** Service layer واضحة: OpenCodeService لإنشاء/استئناف session وإرسال message وقراءة events/files/status حسب API المتاح.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py binds per-workspace local process with separate HOME/XDG, Basic auth and directory; owned route lookup.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Trusted local development only; no OS/network isolation, quotas, durable task recovery or retention. Health/status are auth-scoped global diagnostics, not workspace calls.

### R10.04 — section 10, source line 269

- **Requirement:** كل طلب إلى OpenCode يمر بعد require_user + workspace ownership check.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py binds per-workspace local process with separate HOME/XDG, Basic auth and directory; owned route lookup.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Trusted local development only; no OS/network isolation, quotas, durable task recovery or retention. Health/status are auth-scoped global diagnostics, not workspace calls.

### R10.05 — section 10, source line 271

- **Requirement:** عدم مشاركة auth.json أو DB/session state بين مستخدمين في الإطلاق العام.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py binds per-workspace local process with separate HOME/XDG, Basic auth and directory; owned route lookup.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Trusted local development only; no OS/network isolation, quotas, durable task recovery or retention. Health/status are auth-scoped global diagnostics, not workspace calls.

### R10.06 — section 10, source line 273

- **Requirement:** للإطلاق العام: process/container context مستقل لكل Workspace أو worker boundary لا يسمح بقراءة مساحات الآخرين.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py binds per-workspace local process with separate HOME/XDG, Basic auth and directory; owned route lookup.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Trusted local development only; no OS/network isolation, quotas, durable task recovery or retention. Health/status are auth-scoped global diagnostics, not workspace calls.

### R10.07 — section 10, source line 275

- **Requirement:** Gateway endpoint يعرض health/status الحقيقي؛ لا تظهر OpenCode Ready إلا إذا تحقق الخادم فعليًا.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Internal OPENCODE_URL, authenticated health/status, frontend session state; actual local /global/health and /doc inspected.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Runtime 1.18.31 only. Browser uses Gateway APIs; shared 4096 process is health-only. Public network exposure not assessed.

### R10.08 — section 10.1, source line 279

- **Requirement:** في بيئة التطوير يمكن استخدام instance داخلي محدود، لكن قبل تعدد المستخدمين يجب ألا يعتمد النظام على OpenCode واحد مشترك بسياق filesystem/auth واحد.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py binds per-workspace local process with separate HOME/XDG, Basic auth and directory; owned route lookup.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Trusted local development only; no OS/network isolation, quotas, durable task recovery or retention. Health/status are auth-scoped global diagnostics, not workspace calls.

### R10.09 — section 10.1, source line 281

- **Requirement:** النموذج المستهدف: Workspace A → OpenCode context/process A، Workspace B → OpenCode context/process B، مع منافذ داخلية أو worker identifiers غير مكشوفة للعامة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py binds per-workspace local process with separate HOME/XDG, Basic auth and directory; owned route lookup.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Trusted local development only; no OS/network isolation, quotas, durable task recovery or retention. Health/status are auth-scoped global diagnostics, not workspace calls.

### R10.10 — section 10.1, source line 283

- **Requirement:** كل instance/context يبدأ مع Workspace الخاص به كدليل عمل فعلي، ولا يملك صلاحية تصفح مساحة مستخدم آخر.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py binds per-workspace local process with separate HOME/XDG, Basic auth and directory; owned route lookup.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Trusted local development only; no OS/network isolation, quotas, durable task recovery or retention. Health/status are auth-scoped global diagnostics, not workspace calls.

### R10.11 — section 10.1, source line 285

- **Requirement:** OpenCode Web UI الأصلية على 4096 تبقى أداة اختبار/إدارة أثناء التطوير فقط؛ العميل النهائي يتعامل مع Gateway UI وGateway API.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Internal OPENCODE_URL, authenticated health/status, frontend session state; actual local /global/health and /doc inspected.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Runtime 1.18.31 only. Browser uses Gateway APIs; shared 4096 process is health-only. Public network exposure not assessed.

### R10.12 — section 10.1, source line 287

- **Requirement:** عند توقف أو حذف Workspace تُوقف عملية OpenCode التابعة له وتُمسح الأسرار والملفات المؤقتة وفق سياسة الاحتفاظ.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py binds per-workspace local process with separate HOME/XDG, Basic auth and directory; owned route lookup.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Trusted local development only; no OS/network isolation, quotas, durable task recovery or retention. Health/status are auth-scoped global diagnostics, not workspace calls.

### R11.01 — section 11.1, source line 293

- **Requirement:** بعد التحقق من المستخدم والاشتراك وصلاحية المستودع، ينشئ Workspace Manager مساحة معزولة، ينسخ branch ويحدد base SHA، ثم يبدأ OpenCode في هذا المسار فقط.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R11.02 — section 11.2, source line 297

- **Requirement:** يحفظ backend حالة task/conversation/events لإعادة الاتصال.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R11.03 — section 11.2, source line 299

- **Requirement:** كل Git command ينفذ باسم Workspace وليس بمجلدات المنصة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Git subprocess argv, workspace cwd, no hooks/global credentials/file protocol; OpenCode --pure, ask permissions, external_directory deny.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Not a security sandbox. Untrusted runtime code/network/config needs full isolation and concurrency hardening before public use.

### R11.04 — section 11.2, source line 301

- **Requirement:** لا تنفذ Git hooks غير موثوقة تلقائيًا؛ submodules/SSH dependencies تحتاج سياسة واضحة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Git subprocess argv, workspace cwd, no hooks/global credentials/file protocol; OpenCode --pure, ask permissions, external_directory deny.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Not a security sandbox. Untrusted runtime code/network/config needs full isolation and concurrency hardening before public use.

### R11.05 — section 11.2, source line 303

- **Requirement:** يوفر Restore Point أو patch عند الإمكان قبل تغييرات واسعة.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R11.06 — section 11.3, source line 307

- **Requirement:** المستخدم يرى Files/Diff/Logs/tests قبل commit.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R11.07 — section 11.3, source line 309

- **Requirement:** Commit يحتاج رسالة واضحة ويمكن أن ينشئ working branch تلقائيًا حسب السياسة.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/workspaces.py, routes/workspaces.py; test_workspaces.py and browser flow exercise actual files, Git diff and commit.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/HTML/Python/Node templates verified. No remote push claim.

### R11.08 — section 11.3, source line 311

- **Requirement:** Push المباشر إلى main ليس الافتراضي؛ PR هو المسار الأكثر أمانًا عندما يناسب.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual local Git commits; push endpoint returns 503 without attempting; deletion returns 409 preserving files.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No GitHub transport, remote SHA verification, conflict flow, PR or cleanup implementation.

### R11.09 — section 11.3, source line 313

- **Requirement:** لا force push تلقائي، ولا merge تلقائي من agent.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Git subprocess argv, workspace cwd, no hooks/global credentials/file protocol; OpenCode --pure, ask permissions, external_directory deny.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Not a security sandbox. Untrusted runtime code/network/config needs full isolation and concurrency hardening before public use.

### R11.10 — section 11.3, source line 315

- **Requirement:** إذا تغير remote branch منذ بدء الجلسة، تُكشف conflicts قبل push ولا يُخفى الفشل عن المستخدم.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R11.11 — section 11.3, source line 317

- **Requirement:** بعد push يتحقق Gateway أن expected commit موجود على GitHub وأن working tree نظيف قبل cleanup.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R12.01 — section 12.1, source line 323

- **Requirement:** المعاينة خاصة بالمستخدم، لا port عام دائم لكل مشروع.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R12.02 — section 12.1, source line 325

- **Requirement:** MVP يدعم نطاقًا معلنًا مثل static / Node / Python فقط، ولا يعد بتشغيل كل stack.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R12.03 — section 12.1, source line 327

- **Requirement:** المشاريع التي تحتاج DB تستخدم DB مؤقتة/اختبارية ولا تتصل بproduction تلقائيًا.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R12.04 — section 12.1, source line 329

- **Requirement:** عند الإطلاق بنطاق: preview origin منفصل وtoken قصير العمر/CSP حتى لا يسرق كود المشروع جلسة Gateway.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R12.05 — section 12.2, source line 333

- **Requirement:** رفع صور/ملفات إلى Workspace بعد المصادقة وownership check.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R12.06 — section 12.2, source line 335

- **Requirement:** حد للحجم وallowlist/denylist للأنواع الخطرة حسب الاستخدام.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R12.07 — section 12.2, source line 337

- **Requirement:** اسم داخلي مولد؛ original filename metadata فقط.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R12.08 — section 12.2, source line 339

- **Requirement:** منع path traversal والكتابة خارج repo/workspace.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R12.09 — section 12.2, source line 341

- **Requirement:** metadata: upload id, user id, workspace id, original name, stored path, mime, size, created_at.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R12.10 — section 12.2, source line 343

- **Requirement:** تحذف uploads المؤقتة مع Workspace أو حسب سياسة retention.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R13.01 — section 13, source line 349

- **Requirement:** يحفظ كل event بترتيب sequence/event_id.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R13.02 — section 13, source line 351

- **Requirement:** SSE هو الخيار الأول لstreaming من الخادم للمتصفح؛ WebSocket يضاف إذا احتجنا تحكم ثنائي لحظي.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R13.03 — section 13, source line 353

- **Requirement:** عند reconnect يرسل العميل آخر event_id، والخادم يكمل من هناك بدل تكرار المهمة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R13.04 — section 13, source line 355

- **Requirement:** إغلاق tab لا يساوي حذف Workspace أو إلغاء task تلقائيًا.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R13.05 — section 13, source line 357

- **Requirement:** زر Stop يرسل cancel حقيقي ويظهر النتيجة بوضوح.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R14.01 — section 14.1, source line 363

- **Requirement:** القيم النهائية تعتمد على مواصفات VPS والباقات، لكن يجب أن توجد حدود صريحة قبل تعدد المستخدمين.
- **Status:** BLOCKED
- **Phase:** MVP / phased
- **Evidence / files / tests:** No public deployment is authorized.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resource/billing limits require policy decisions and target capacity before public launch.

### R14.02 — section 14.2, source line 369

- **Requirement:** Temporary session: cleanup بعد push مؤكد وإنهاء المستخدم.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R14.03 — section 14.2, source line 371

- **Requirement:** Resumable workspace: 14/30 يومًا حسب الباقة من آخر نشاط أو تاريخ محدد بوضوح.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R14.04 — section 14.2, source line 373

- **Requirement:** Countdown وتنبيه قبل expiry.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R14.05 — section 14.2, source line 375

- **Requirement:** إذا Push فشل أو الاشتراك انتهى: grace period لاسترداد العمل/patch، ولا حذف مفاجئ.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R14.06 — section 14.2, source line 377

- **Requirement:** Cleanup job يسجل الوقت والحالة والسبب فقط، لا يحتفظ بالكود في audit log.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R15.01 — section 15, source line 381

- **Requirement:** Account منفصل عن Workspace: profile، GitHub connection، provider settings، devices/sessions، language/theme، subscription/trial.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Database profile/trial fields and preference PATCH connected. Hardcoded billing dates removed.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No enforced entitlements, provider account connections, device management, profile editing UI or payment lifecycle.

### R15.02 — section 15, source line 383

- **Requirement:** التجربة المجانية 10 أيام من تفعيل الحساب، بسياسة تمنع تكرارها بطريقة بسيطة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Database profile/trial fields and preference PATCH connected. Hardcoded billing dates removed.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No enforced entitlements, provider account connections, device management, profile editing UI or payment lifecycle.

### R15.03 — section 15, source line 385

- **Requirement:** كل Plan له version محفوظ: price, duration, runtime quota, storage, concurrent sessions, retention, features.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R15.04 — section 15, source line 387

- **Requirement:** تكلفة API الخارجية منفصلة. Usage platform قد يعتمد runtime/storage/quota معلنة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Architecture policy retained; see ARCHITECTURE.md and SECURITY_MODEL.md.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Policy statements are not evidence that all future runtime/payment enforcement is implemented.

### R15.05 — section 15, source line 389

- **Requirement:** PayPal/Bank transfer لا تعتبر حقيقية حتى توجد integration/webhooks/storage للreceipts.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R15.06 — section 15, source line 391

- **Requirement:** Ledger مالي append-only نسبيًا: كل تعديل رصيد له سبب وفاعل ومرجع؛ webhook المكرر لا يزيد الرصيد مرتين.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R15.07 — section 15, source line 393

- **Requirement:** الأسعار النهائية لا تعتمد قبل قياس تكلفة التشغيل الفعلية.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Architecture policy retained; see ARCHITECTURE.md and SECURITY_MODEL.md.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Policy statements are not evidence that all future runtime/payment enforcement is implemented.

### R16.01 — section 16.1, source line 401

- **Requirement:** إنشاء أول Owner يتم عبر trusted bootstrap script/command على الخادم أو إجراء موثوق، وليس من نموذج التسجيل العام.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Server admin/owner authorization, real user list and overview counts retained.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Support/finance roles, audited owner bootstrap, admin mutations/export remain missing.

### R16.02 — section 16.2, source line 405

- **Requirement:** Registered/Active/Trial/Expired تُحسب من PostgreSQL queries الحقيقية.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual DB user aggregates. No invented payments, visitor or resource counters in active UI.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement audited metrics/operations only when real sources exist.

### R16.03 — section 16.2, source line 407

- **Requirement:** Payments/Revenue لا تظهر رقمًا إلا من ledger/payments الحقيقي.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual DB user aggregates. No invented payments, visitor or resource counters in active UI.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement audited metrics/operations only when real sources exist.

### R16.04 — section 16.2, source line 409

- **Requirement:** Visitors لا تظهر إلا إذا كان telemetry/analytics موجودًا ومعلنًا.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual DB user aggregates. No invented payments, visitor or resource counters in active UI.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement audited metrics/operations only when real sources exist.

### R16.05 — section 16.2, source line 411

- **Requirement:** OpenCode status يأتي من health endpoint الحقيقي.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R16.06 — section 16.2, source line 413

- **Requirement:** Sessions تأتي من workspace/session records الفعلية.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual DB user aggregates. No invented payments, visitor or resource counters in active UI.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement audited metrics/operations only when real sources exist.

### R16.07 — section 16.2, source line 415

- **Requirement:** أي metric غير منفذة تظهر Not available yet أو Preview ولا تستخدم أرقامًا مزيفة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual DB user aggregates. No invented payments, visitor or resource counters in active UI.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement audited metrics/operations only when real sources exist.

### R16.08 — section 16.3, source line 419

- **Requirement:** عرض active workspaces, queue, CPU, RAM, disk, errors, failed clone/push/cleanup.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R16.09 — section 16.3, source line 421

- **Requirement:** إيقاف session مسيئة أو تجاوزت limits مع audit reason.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R16.10 — section 16.3, source line 423

- **Requirement:** Audit logs لإجراءات الإدارة والدفع والصلاحيات، دون أسرار أو source code.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R16.11 — section 16.3, source line 425

- **Requirement:** MFA/تحقق إضافي لحسابات Owner/Admin قبل الإطلاق التجاري.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R17.01 — section 17.1, source line 431

- **Requirement:** Container/sandbox مستقل لكل Workspace في التشغيل العام، بلا root أو privileged.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R17.02 — section 17.1, source line 433

- **Requirement:** عدم ربط Docker socket داخل workspace.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R17.03 — section 17.1, source line 435

- **Requirement:** عدم mount لمجلدات host الحساسة.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R17.04 — section 17.1, source line 437

- **Requirement:** Network policy تمنع الوصول إلى PostgreSQL المنصة وmetadata services ولوحات الإدارة.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R17.05 — section 17.1, source line 439

- **Requirement:** المستودع غير موثوق: لا تُنفذ MCP/config/hooks/instructions منه بصلاحيات واسعة تلقائيًا.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Git subprocess argv, workspace cwd, no hooks/global credentials/file protocol; OpenCode --pure, ask permissions, external_directory deny.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Not a security sandbox. Untrusted runtime code/network/config needs full isolation and concurrency hardening before public use.

### R17.06 — section 17.2, source line 443

- **Requirement:** Workspace root هو الحد الأعلى لكل file API.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/workspaces.py path validation; traversal/absolute path/symlink and ownership regression tests.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** File API boundary verified locally. OS process isolation remains a separate launch blocker.

### R17.07 — section 17.2, source line 445

- **Requirement:** رفض absolute paths و.. بعد canonicalization.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/workspaces.py path validation; traversal/absolute path/symlink and ownership regression tests.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** File API boundary verified locally. OS process isolation remains a separate launch blocker.

### R17.08 — section 17.2, source line 447

- **Requirement:** فحص symlink target قبل القراءة والكتابة.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/workspaces.py path validation; traversal/absolute path/symlink and ownership regression tests.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** File API boundary verified locally. OS process isolation remains a separate launch blocker.

### R17.09 — section 17.2, source line 449

- **Requirement:** عدم عرض /home/tahir أو .ssh أو .config أو OpenCode runtime الداخلي للمستخدم.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit public asset allowlist; sanitized runtime errors; secure cookie default; loopback local mode; .env.example and deployment templates.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Private source static exposure fixed. Comprehensive credential redaction, HTTPS deployment and rate limits unverified or missing.

### R17.10 — section 17.3, source line 453

- **Requirement:** تشفير provider credentials وGitHub secrets at rest بمفتاح منفصل عن DB.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R17.11 — section 17.3, source line 455

- **Requirement:** عدم logging للtokens/passwords/API keys.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit public asset allowlist; sanitized runtime errors; secure cookie default; loopback local mode; .env.example and deployment templates.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Private source static exposure fixed. Comprehensive credential redaction, HTTPS deployment and rate limits unverified or missing.

### R17.12 — section 17.3, source line 457

- **Requirement:** حقن credential فقط وقت العملية ومسحه/إبطال token عند انتهاء الجلسة.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R17.13 — section 17.3, source line 459

- **Requirement:** HTTPS إلزامي عند الإطلاق، rate limits ومحاولات دخول محدودة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit public asset allowlist; sanitized runtime errors; secure cookie default; loopback local mode; .env.example and deployment templates.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Private source static exposure fixed. Comprehensive credential redaction, HTTPS deployment and rate limits unverified or missing.

### R18.01 — section 18, source line 463

- **Requirement:** PostgreSQL يخزن metadata وبيانات المنصة فقط. Source code، artifacts التنفيذية، وworkspaces تبقى في filesystem/object storage المؤقت حسب السياسة.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Nine application tables; no repository content or raw tokens in metadata DB; schema generated below.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Only implemented phase tables exist. Runtime stores conversation/content locally; later retention and secret policies required.

### R18.02 — section 18, source line 467

- **Requirement:** كل سجل مرتبط بالمستخدم/Workspace يحتاج ownership key وفهارس وقيود تمنع الوصول المتقاطع. Password hashes وsession token hashes فقط؛ لا plaintext passwords.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Nine application tables; no repository content or raw tokens in metadata DB; schema generated below.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Only implemented phase tables exist. Runtime stores conversation/content locally; later retention and secret policies required.

### R18.03 — section 18.1, source line 471

- **Requirement:** projects: id, user_id, name, source_type(github|blank|template), github_connection_id/repository_id عند توفره، default_branch، created_at.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R18.04 — section 18.1, source line 473

- **Requirement:** workspaces: id, project_id, user_id, local_path الداخلي، status، base_commit_sha، created_at، last_activity_at، expires_at، runtime/opencode reference.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R18.05 — section 18.1, source line 475

- **Requirement:** workspace_sessions: id, workspace_id, user_id, opencode_session_id، title/status، created_at، last_activity_at.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R18.06 — section 18.1, source line 477

- **Requirement:** لا يُعاد local_path الحقيقي إلى العميل؛ يستخدم backend workspace_id ويحل المسار داخليًا بعد ownership check.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R18.07 — section 18.2, source line 481

- **Requirement:** POST /api/workspaces لإنشاء Workspace من GitHub أو Blank أو Template.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R18.08 — section 18.2, source line 483

- **Requirement:** GET /api/workspaces وGET /api/workspaces/{id} لعرض المساحات المملوكة للمستخدم فقط.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R18.09 — section 18.2, source line 485

- **Requirement:** DELETE /api/workspaces/{id} لإنهاء/حذف Workspace وفق policy وبعد حماية العمل غير المرفوع.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R18.10 — section 18.2, source line 487

- **Requirement:** POST /api/workspaces/{id}/sessions لإنشاء Session جديدة على Workspace موجود.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R19.01 — section 19.1, source line 495

- **Requirement:** لا تُحفظ القيم الحقيقية في Git. .env يبقى 0600 ويستبعد من المستودع، وتستخدم .env.example بأسماء ومتغيرات دون أسرار.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit public asset allowlist; sanitized runtime errors; secure cookie default; loopback local mode; .env.example and deployment templates.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Private source static exposure fixed. Comprehensive credential redaction, HTTPS deployment and rate limits unverified or missing.

### R20.01 — section 20.1, source line 507

- **Requirement:** Register/Login/session حقيقي
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Auth and profile APIs wired to frontend; case-insensitive login, null validation and owner/admin access fixed.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Password reset, verification, rate limiting and expanded roles remain absent.

### R20.02 — section 20.1, source line 509

- **Requirement:** GitHub App وربط repo/branch حقيقي
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.03 — section 20.1, source line 511

- **Requirement:** إنشاء مشروع من الصفر Blank Project وإنشاء مشروع من Template مدعوم، دون الحاجة إلى GitHub في لحظة البدء.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R20.04 — section 20.1, source line 513

- **Requirement:** Workspace Manager حقيقي ينشئ filesystem workspace ويعيد ربط OpenCode به بدل فتح OpenCode الخام.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R20.05 — section 20.1, source line 515

- **Requirement:** فصل New Project عن New Session؛ جلسات متعددة يمكنها العمل على نفس Workspace.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py; test_real_opencode_new_session_retains_files starts installed OpenCode 1.18.31 and creates two distinct runtime sessions on one workspace.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Requires OPENCODE_RUNTIME_MODE=local. Provider-backed edits are not covered by this test.

### R20.06 — section 20.1, source line 517

- **Requirement:** Workspace واحد معزول لمستخدم واحد
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.07 — section 20.1, source line 519

- **Requirement:** ربط OpenCode الحقيقي وإرسال prompt واستقبال events
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R20.08 — section 20.1, source line 521

- **Requirement:** Files/Diff/Logs حقيقية
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R20.09 — section 20.1, source line 523

- **Requirement:** Commit/Push إلى branch الصحيح والتحقق من النتيجة
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual local Git commits; push endpoint returns 503 without attempting; deletion returns 409 preserving files.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No GitHub transport, remote SHA verification, conflict flow, PR or cleanup implementation.

### R20.10 — section 20.1, source line 525

- **Requirement:** Basic account/trial
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Database profile/trial fields and preference PATCH connected. Hardcoded billing dates removed.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No enforced entitlements, provider account connections, device management, profile editing UI or payment lifecycle.

### R20.11 — section 20.1, source line 527

- **Requirement:** Basic admin users/status الحقيقي
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Server admin/owner authorization, real user list and overview counts retained.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Support/finance roles, audited owner bootstrap, admin mutations/export remain missing.

### R20.12 — section 20.1, source line 529

- **Requirement:** Cleanup آمن بعد success
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.13 — section 20.1, source line 531

- **Requirement:** Mobile usable flow
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** index.html/styles.css/app.js; desktop/mobile Playwright, Arabic/English, light/dark, real SVG brand marks.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Working responsive workspace layout. Public legal/support content, full admin localization and some accessibility refinements remain.

### R20.14 — section 20.2, source line 535

- **Requirement:** Preview runner لمشاريع محددة
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.15 — section 20.2, source line 537

- **Requirement:** Reconnect/resume متقدم
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.16 — section 20.2, source line 539

- **Requirement:** Resource quotas/queue
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.17 — section 20.2, source line 541

- **Requirement:** Retention tiers/grace period
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.18 — section 20.2, source line 543

- **Requirement:** Full account devices/sessions
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.19 — section 20.2, source line 545

- **Requirement:** Admin operational dashboard
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual DB user aggregates. No invented payments, visitor or resource counters in active UI.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement audited metrics/operations only when real sources exist.

### R20.20 — section 20.2, source line 547

- **Requirement:** Activity/security logs
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.21 — section 20.3, source line 551

- **Requirement:** PayPal production integration
- **Status:** MISSING
- **Phase:** Future / optional
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.22 — section 20.3, source line 553

- **Requirement:** Bank receipts workflow
- **Status:** MISSING
- **Phase:** Future / optional
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.23 — section 20.3, source line 555

- **Requirement:** Wallet/ledger advanced
- **Status:** MISSING
- **Phase:** Future / optional
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.24 — section 20.3, source line 557

- **Requirement:** Coupons/offers
- **Status:** MISSING
- **Phase:** Future / optional
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.25 — section 20.3, source line 559

- **Requirement:** PR automation advanced
- **Status:** MISSING
- **Phase:** Future / optional
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.26 — section 20.3, source line 561

- **Requirement:** More runtime stacks
- **Status:** MISSING
- **Phase:** Future / optional
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.27 — section 20.3, source line 563

- **Requirement:** Team collaboration
- **Status:** MISSING
- **Phase:** Future / optional
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.28 — section 20.3, source line 565

- **Requirement:** Advanced analytics
- **Status:** MISSING
- **Phase:** Future / optional
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R20.29 — section 20.4, source line 569

- **Requirement:** تشغيل كل أنواع المشاريع
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit scope exclusion retained in roadmap.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No excluded infrastructure/product promised; revisit only if user changes scope.

### R20.30 — section 20.4, source line 571

- **Requirement:** استضافة Git دائمة بدل GitHub
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit scope exclusion retained in roadmap.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No excluded infrastructure/product promised; revisit only if user changes scope.

### R20.31 — section 20.4, source line 573

- **Requirement:** فتح OpenCode الخام لكل مستخدم
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit scope exclusion retained in roadmap.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No excluded infrastructure/product promised; revisit only if user changes scope.

### R20.32 — section 20.4, source line 575

- **Requirement:** الوصول إلى production databases تلقائيًا
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit scope exclusion retained in roadmap.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No excluded infrastructure/product promised; revisit only if user changes scope.

### R20.33 — section 20.4, source line 577

- **Requirement:** Unlimited compute/storage
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit scope exclusion retained in roadmap.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No excluded infrastructure/product promised; revisit only if user changes scope.

### R20.34 — section 20.4, source line 579

- **Requirement:** Multi-user live collaboration في نفس Workspace
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit scope exclusion retained in roadmap.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No excluded infrastructure/product promised; revisit only if user changes scope.

### R20.35 — section 20.4, source line 581

- **Requirement:** ضمان استمرار أي provider/model مجاني
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Explicit scope exclusion retained in roadmap.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No excluded infrastructure/product promised; revisit only if user changes scope.

### R21.01 — section 21, source line 587

- **Requirement:** Auth + GitHub App + repo/branch + Blank/Template project creation + Workspace Manager + isolated workspace + OpenCode API/runtime binding + real agent stream + multiple sessions per workspace + files/diff/logs + commit/push verified. هذه هي الأولوية الحالية قبل أي تجميل أو دفع متقدم.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Auth and profile APIs wired to frontend; case-insensitive login, null validation and owner/admin access fixed.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Password reset, verification, rate limiting and expanded roles remain absent.

### R21.02 — section 21, source line 591

- **Requirement:** Container/sandbox isolation، resource limits، preview للstacks المدعومة، stop/reconnect، cleanup/retention، activity logs، account/admin الفعلي.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R21.03 — section 21, source line 595

- **Requirement:** Plan versions، payments/PayPal/bank، ledger، coupons، notifications، advanced reports، PR flows، قياس تكلفة التشغيل وتوسيع runtime stacks.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R22.01 — section 22, source line 599

- **Requirement:** الزائر يرى Landing ولا يستطيع فتح Workspace أو Account أو Admin دون session صحيحة.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Auth routes, schemas/account.py, app.js; security/account tests and browser authentication flow.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Registration, cookie sessions and startup guards verified locally; no production claim.

### R22.02 — section 22, source line 601

- **Requirement:** لا يستطيع الزائر أو المستخدم فتح OpenCode على 4096 مباشرة في بيئة الإنتاج.
- **Status:** BLOCKED
- **Phase:** MVP / phased
- **Evidence / files / tests:** Production state intentionally not inspected under local-only instruction. Local workspace creation works.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Review production only after explicit authorization; this does not block local development.

### R22.03 — section 22, source line 603

- **Requirement:** مستخدمان لا يستطيعان قراءة ملفات أو sessions أو credentials بعضهما.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R22.04 — section 22, source line 605

- **Requirement:** اختيار repository وbranch يأتي من GitHub الحقيقي ويغير clone/workspace فعليًا.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R22.05 — section 22, source line 607

- **Requirement:** الـbase commit SHA الظاهر يطابق GitHub وقت بدء العمل.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R22.06 — section 22, source line 609

- **Requirement:** Prompt يصل إلى OpenCode الحقيقي وتظهر events حقيقية لا نصوص static.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R22.07 — section 22, source line 611

- **Requirement:** Files/Diff/Logs تعكس filesystem/Git الحقيقي للWorkspace.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R22.08 — section 22, source line 613

- **Requirement:** الأمر الحساس ينتظر approval ويستطيع المستخدم إيقاف task.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R22.09 — section 22, source line 615

- **Requirement:** بعد انقطاع الاتصال يمكن العودة إلى نفس task دون تكرار التنفيذ.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/agent.py, execution_events, EventSource frontend, scoped approval details/stop; unit boundary tests use mocked runtime.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Real transport is implemented, but no provider-authenticated model edit/test E2E. Only Gateway lifecycle events; no token/tool-progress bridge, replay/task crash recovery or idempotency proof.

### R22.10 — section 22, source line 617

- **Requirement:** Commit ينشأ في repo الصحيح، وPush يصل إلى branch الصحيح.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual local Git commits; push endpoint returns 503 without attempting; deletion returns 409 preserving files.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No GitHub transport, remote SHA verification, conflict flow, PR or cleanup implementation.

### R22.11 — section 22, source line 619

- **Requirement:** فشل Push أو conflict يمنع cleanup الذي قد يفقد العمل.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Actual local Git commits; push endpoint returns 503 without attempting; deletion returns 409 preserving files.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** No GitHub transport, remote SHA verification, conflict flow, PR or cleanup implementation.

### R22.12 — section 22, source line 621

- **Requirement:** بعد Push ناجح يتحقق Gateway من remote commit ثم ينظف حسب policy.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R22.13 — section 22, source line 623

- **Requirement:** لا يخرج file API من workspace root حتى مع ../ أو symlink.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/workspaces.py path validation; traversal/absolute path/symlink and ownership regression tests.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** File API boundary verified locally. OS process isolation remains a separate launch blocker.

### R22.14 — section 22, source line 625

- **Requirement:** GitHub/API credentials لا تظهر في browser storage أو logs أو DB بصيغة plaintext.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R22.15 — section 22, source line 627

- **Requirement:** Admin metrics إما حقيقية من DB/runtime أو موصوفة بوضوح بأنها غير متاحة؛ لا أرقام وهمية.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** routes/admin.py overview and user list; preserved existing admin regression test.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** User counts come from DB. Payment and visitor metrics explicitly unavailable.

### R22.16 — section 22, source line 629

- **Requirement:** تعديل plan مستقبلي لا يغير plan_version لاشتراك سابق، وwebhook دفع مكرر لا يكرر الرصيد.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R22.17 — section 22, source line 631

- **Requirement:** يستطيع المستخدم إنشاء Blank Project دون GitHub، ويظهر Workspace حقيقي يمكن لـOpenCode قراءة ملفاته وإنشاء ملفات جديدة داخله.
- **Status:** PARTIAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Project/Workspace models, migration 0002_workspaces, owned filesystem service, connected frontend.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Local Blank/Template works. GitHub source, first-session automation, source/base SHA display, entitlement gates and OS sandbox are incomplete as applicable.

### R22.18 — section 22, source line 633

- **Requirement:** يستطيع المستخدم إنشاء New Session على Project موجود دون إنشاء Workspace جديد أو فقد الملفات الحالية.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** services/opencode.py; test_real_opencode_new_session_retains_files starts installed OpenCode 1.18.31 and creates two distinct runtime sessions on one workspace.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Requires OPENCODE_RUNTIME_MODE=local. Provider-backed edits are not covered by this test.

### R22.19 — section 22, source line 635

- **Requirement:** يستطيع المشروع الجديد الارتباط لاحقًا بـGitHub ثم Commit/Push إلى repository يختاره المستخدم ضمن الصلاحيات.
- **Status:** MISSING
- **Phase:** MVP / phased
- **Evidence / files / tests:** No complete implementation of this requirement in the current phase.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Implement in priority order; see DEVELOPMENT_ROADMAP.md.

### R22.20 — section 22, source line 637

- **Requirement:** لا تظهر شاشة OpenCode الأصلية أو متصفح filesystem للمستخدم النهائي، ولا تعتمد المنصة على Add project اليدوي داخل OpenCode.
- **Status:** REAL
- **Phase:** MVP / phased
- **Evidence / files / tests:** Internal OPENCODE_URL, authenticated health/status, frontend session state; actual local /global/health and /doc inspected.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Runtime 1.18.31 only. Browser uses Gateway APIs; shared 4096 process is health-only. Public network exposure not assessed.

### R23.01 — section 23, source line 641

- **Requirement:** اسم النطاق النهائي.
- **Status:** BLOCKED
- **Phase:** Decision
- **Evidence / files / tests:** Open product/launch decision in the source document.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resolve before the affected phase; never infer an accepted decision.

### R23.02 — section 23, source line 643

- **Requirement:** مواصفات VPS/worker capacity وعدد المستخدمين المتزامنين المتوقع.
- **Status:** BLOCKED
- **Phase:** Decision
- **Evidence / files / tests:** Open product/launch decision in the source document.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resolve before the affected phase; never infer an accepted decision.

### R23.03 — section 23, source line 645

- **Requirement:** حدود CPU/RAM/disk/runtime لكل Plan.
- **Status:** BLOCKED
- **Phase:** Decision
- **Evidence / files / tests:** Open product/launch decision in the source document.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resolve before the affected phase; never infer an accepted decision.

### R23.04 — section 23, source line 647

- **Requirement:** مدة retention/grace period.
- **Status:** BLOCKED
- **Phase:** Decision
- **Evidence / files / tests:** Open product/launch decision in the source document.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resolve before the affected phase; never infer an accepted decision.

### R23.05 — section 23, source line 649

- **Requirement:** الstacks المدعومة في Preview.
- **Status:** BLOCKED
- **Phase:** Decision
- **Evidence / files / tests:** Open product/launch decision in the source document.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resolve before the affected phase; never infer an accepted decision.

### R23.06 — section 23, source line 651

- **Requirement:** GitHub App permissions النهائية وWebhook URL.
- **Status:** BLOCKED
- **Phase:** Decision
- **Evidence / files / tests:** Open product/launch decision in the source document.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resolve before the affected phase; never infer an accepted decision.

### R23.07 — section 23, source line 653

- **Requirement:** مزودات AI المسموح حفظ credentials لها ونوع المصادقة لكل مزود.
- **Status:** BLOCKED
- **Phase:** Decision
- **Evidence / files / tests:** Open product/launch decision in the source document.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resolve before the affected phase; never infer an accepted decision.

### R23.08 — section 23, source line 655

- **Requirement:** الأسعار والحصص بعد قياس تكلفة التشغيل.
- **Status:** BLOCKED
- **Phase:** Decision
- **Evidence / files / tests:** Open product/launch decision in the source document.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resolve before the affected phase; never infer an accepted decision.

### R23.09 — section 23, source line 657

- **Requirement:** حساب PayPal التجاري والبنك عند الوصول لمرحلة الدفع.
- **Status:** BLOCKED
- **Phase:** Decision
- **Evidence / files / tests:** Open product/launch decision in the source document.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resolve before the affected phase; never infer an accepted decision.

### R23.10 — section 23, source line 659

- **Requirement:** سياسة الخصوصية وشروط الاستخدام وسياسة حذف البيانات.
- **Status:** BLOCKED
- **Phase:** Decision
- **Evidence / files / tests:** Open product/launch decision in the source document.
- **API / DB:** See exact implemented inventory in API_REFERENCE.md and DATABASE_REFERENCE.md; absence there is not implied implementation.
- **Gap / next action:** Resolve before the affected phase; never infer an accepted decision.


Registration update (2026-10-04): username minimum 6, password minimum 8 with number and punctuation symbol; no uppercase requirement, existing logins unchanged. See API_REFERENCE.md. No migration.
