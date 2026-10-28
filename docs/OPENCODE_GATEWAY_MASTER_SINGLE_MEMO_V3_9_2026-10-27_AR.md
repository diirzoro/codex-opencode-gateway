# OpenCode Gateway — المذكرة الرئيسية الموحدة: المعمارية والحماية والأداء وGitHub وPreview
**الإصدار V3.9 — 27 أكتوبر 2026 | المرجع التنفيذي الموحد | TEST و`updates` فقط**
**حالة الوثيقة:** المرجع الوحيد للعمل الجديد؛ تحتفظ الأقسام التاريخية أدناه بأدلتها وتواريخها، ولكن قسم «القرارات المحدثة» في آخر المذكرة يحسم أي تعارض بين الخطة القديمة والحالية.
**نطاق التحديث:** المكتبة فقط؛ نسخة v3.4 السابقة مؤرشفة، والسجلات التاريخية لا تُعد أوامر تنفيذ حديثة.

## 1. قرارات المالك النهائية غير القابلة للتجاوز
- **TEST و`updates` فقط.** لا خطة نقل أو دمج إلى `master`، ولا تعديل أو تشغيل أو نشر LIVE، ولا تعديل Preview أو إعادة تصميم Dashboard/Workspace.
- Python/FastAPI **يبقى** Control Plane: حسابات المستخدمين، تسجيل الدخول، الأدوار وصلاحية مدير المشروع، الاشتراكات والحصص، إنشاء/ملكية المشاريع وWorkspaces والجلسات، تحديد مسار الملفات، إدارة وربط ملكية بيانات الاعتماد وOAuth/GitHub، الإدارة والتدقيق. PostgreSQL لبيانات Gateway وعلاقات الملكية فقط.
- **OpenCode Native وحده** Data Plane: جلسات ومحادثات ونماذج ومزوّدون ووكلاء وأدوات برمجة وملفات وTodo وأسئلة وموافقات وإيقاف وSSE. لا إنشاء Python AI processor أو queue أو engine أو runtime لكل Workspace، ولا نسخ كتالوج المزوّدين إلى PostgreSQL.
- **محرك OpenCode الحالي مشترك مع LIVE من حيث الخدمة/التثبيت حسب إفادة المالك**؛ لا تلمس خدمته أو مساره أو نسخته أو HOME/XDG أو بياناته أو مخزنه أو منافذه، ولا توقفه أو تعيد تشغيله؛ تحقق من حدود مشاركة التثبيت والتخزين دون افتراض. LIVE متوقف، لكن قد يتأثر بالخدمة/ Nginx المشتركين.
- لا تستخدم `opencode web` أو تنشئ واجهة OpenCode إضافية. استعمل API الأصلي للخادم headless الجاري؛ افحص `ExecStart` قراءة فقط بدل إعادة تثبيت/تحويل خدمة تعمل فعليًا.
- الواجهة/خدمة Gateway المصرح لها تمر من **User → Python authorization → Nginx internal native transport → OpenCode Native → Nginx/SSE → Client**. Python قد يقرأ metadata لازمة للتحقق، لكنه لا يعالج تدفق استجابات AI أو ينفذ أدوات الموديل.
- لا تنشر واجهة تتطلب Native Backend أحدث فوق Backend قديم؛ لا تشغّل نشرًا جزئيًا للحزمة المترابطة. حافظ على الملفات/المفاتيح/البيانات والنسخ الاحتياطية وعدم تجاوز تعديلات المشغّل المجهولة.
- المنصة مصممة لخدمة **جميع المستخدمين المسجّلين والمخوّلين** مع مشاريعهم المنفصلة، لا شخصًا أو مالك TEST معينًا. كون المالك المستخدم الفعلي الوحيد حاليًا وصف لحالة الاختبار السابقة **وليس سياسة قبول أو ترخيصًا لحصر الخدمة**. اختبر عدة حسابات قبل الإطلاق؛ لا تسمح بخرق الهوية والملكية والاعتمادات أو كشف الملفات.

## 2. فصل المسؤوليات والسرعة مع الحماية
| الجهة | المسموح والواجب | الممنوع |
|---|---|---|
| Python Gateway / PostgreSQL | قرار الوصول للملفات والمشاريع والجلسات والأدوار والمفاتيح والتفويض والاشتراك وسياسات المدير | توليد AI، تسيير tool calls، عمل stream proxy أو queue منافس، نسخ كتالوج Native |
| Nginx | internal routing بعد التفويض وSSE، منع عرض Basic credentials والمسارات الداخلية | نشر Native raw endpoints للجمهور، تمرير مجلد يختاره المتصفح |
| OpenCode Native | محرك تنفيذ واحد دائم، جلسات/رسائل/نماذج/Agents/Tools/Todo/Permissions/SSE وتخزينه الأصلي | per-user/per-workspace engine جديد أو OpenCode Web |
| OS/filesystem boundary | عزل مسارات التنفيذ والأسرار وملفات المستخدمين | اعتبار فحص Gateway وحده Sandbox؛ خدمة مشتركة لها حق القراءة لا تعني عزلا متحققا |
- هوية المستخدم ودوره وملكية مشروعه تُشتق من سجلات السيرفر **لا** بارامترات JS أو ملفات مشروع غير موثوقة. تحقق من ملكية User→Project→Workspace→Session لكل طلب Native محمي.
- لا تفترض أن `directory` يفصل credential store أو Shell/OS permissions في عملية Native مشتركة؛ `/auth/{provider}` عام على مستوى العملية في 1.19.4 (مؤكد بتجارب المصدر). كود Gateway الحالي يمنع حسابًا من الاستيلاء على اعتماد حساب آخر، لكنه **لم يحل** دعم مفتاحين مختلفين للمزوّد نفسه لمستخدمين اثنين. لا تخفِ العائق أو تزيل حاجز المنع.
- Shell / bash / terminal / بدائل exec وsubagents **محظورة للمستخدم العادي**، ولا يجوز تفعيلها اعتمادًا على موافقة UI. المدير الحقيقي لمشروع يملكه يمكن السماح له فقط بعد إثبات OS isolation داخل مشروعه؛ الكود الحالي يبقيها محظورة **حتى للمدير**. لا تعتبر هذا العجز نجاحًا كاملًا لمطلب المدير.
- أدوات ملفات Native تُقيد بالمجلد المملوك وترفض external_directory والروابط الرمزية والمسارات غير الآمنة وملفات الإعدادات التنفيذية. ما زال تدقيق OS/TOCTOU مطلوبًا قبل الإطلاق.

## 3. معلومات الربط والتشغيل المحفوظة
| البند | القيمة | حالة التحقق |
|---|---|---|
| GitHub | `diirzoro/codex-opencode-gateway` | مؤكد من GitHub |
| فرع TEST/التطوير | `updates` | معتمد |
| فرع إنتاج الكود | `master` | معتمد |
| TEST URL | `https://test.opencode-gateway.codes/` | موثق في التسليم |
| LIVE URL | `https://opencode-gateway.codes/` | موثق |
| VPS IP | `162.35.127.135` | معلومة تشغيلية سابقة من المالك؛ تأكيد DNS/VPS قبل أي إجراء |
| OS | `Ubuntu 24.04.5 LTS` | معلومة تشغيلية سابقة |
| TEST code path | `/home/tahir/opencode-gateway-test` | موثق |
| TEST Gateway service | `opencode-gateway-test.service` | موثق أنها كانت active في التسليم |
| TEST Native service | `opencode-native-test.service` | موثق أنها كانت active في التسليم |
| Native install path | `/opt/opencode-live` | موثق؛ الاسم التاريخي لا يبرر نقل/إعادة تثبيت |
| TEST PostgreSQL DB | `opencode_gateway_test` | موثق |
| Native loopback | `127.0.0.2:4097` | موثق في وثائق GitHub؛ تحقق من config الفعلي |
| Native discovery Nginx | `127.0.0.1:18097` | موثق |
| Native sessions/SSE Nginx | `127.0.0.1:18098` | موثق |
| Nginx named redirects | `@native_discovery_test`, `@native_session_test` | موثق في التسليم |
| Native authorization route | `/native-session/{workspace_id}/...` | موثق في الكود |
| Gateway Native state route | `/api/native-test/state` | موثق في الكود |
| Native TEST feature flags | `OPENCODE_NATIVE_TEST_ENABLED`, `OPENCODE_NATIVE_TEST_OWNER_ID` | موجودة في كود TEST |
| TEST release private backup | `/var/backups/opencode-native-coordinated-test` | موثق في خطة النشر؛ وجوده فعليًا غير متحقق |
| TEST selective UI backup | `/home/tahir/opencode-test-ui-backups/native-20261023102533` | موثق في تسليم المشغّل |
| Nginx TEST site | `/etc/nginx/sites-available/opencode-gateway-test` | مرجع تخطيط نشر، يحتاج تحقق فعلي |
| Nginx protected session conf | `/etc/nginx/conf.d/opencode-native-test-session-local.conf` | مرجع تخطيط نشر |
| Nginx Native snippet | `/etc/nginx/snippets/opencode-native-coordinated-test.conf` | مرجع تخطيط نشر |
| TEST Gateway activation env | `/etc/opencode-gateway-test/native-release.env` | مرجع تخطيط نشر، لا تكتب مفاتيحه في التقارير |
| TEST systemd drop-in | `/etc/systemd/system/opencode-gateway-test.service.d/zzzz-native-release.conf` | مرجع تخطيط نشر |

**لا تفترض** أن أسماء خدمات أو منافذ LIVE مطابقة لـTEST. مسارات التخزين القديمة المذكورة في الوثائق `/var/lib/opencode-workspaces` و`/var/lib/opencode-runtime` تُحفظ كمرجع؛ تحقق من النسختين ومسارات TEST الفعلية قبل أي تغيير. لا تُطبع `.env` أو Authorization headers أو كلمات السر أو مفاتيح OAuth/API في تقارير الفحص.


## 4. اتصالات المزوّدين وإعدادات Workspace — قاعدة ملزمة
- التسلسل: Dashboard Connections/Settings → Native Auth/Config/Storage عبر Gateway ownership → Workspace يعرض النماذج المسموح بها للمستخدم. الفهرس العام ليس قائمة Connected، وحفظ API Key لا يساوي نجاح اتصال فعلي بنموذج مدفوع.
- في **القائمة الرئيسية** اعرض **50 مزوّدًا على الأكثر**، مع إظهار المتصلين كذلك ولو كانوا خارج الخمسين. بقية فهرس OpenCode يبقى متاحًا عبر Add Provider Manually بالاسم أو Native ID (دون اختراع provider).
- يجب اختبار الربط اليدوي لمزوّد خارج الخمسين، ظهور نماذجه، اختيار نموذج، إرسال استجابة فعلية، وفصل الاتصال. إن لم تتوفر بيانات اعتماد حقيقية فهذا **BLOCKED** وليس PASS.
- لا تولد Credential API ثانٍ في Python: Gateway يدير الملكية والسرية والتفويض، ويستخدم Native auth المعلن. لا تنسخ مفاتيح حساب إلى مخزن global بحيث تفتح حسابًا آخر. عدم دعم مفاتيح متعددة لمزود واحد في shared process مشكلة مفتوحة.

## 5. OpenCode دائم التشغيل / Native Storage First
- خدمة `opencode-native-test.service` الحالية والمحرك headless الموجود دائم التشغيل؛ لا spawn عند login أو فتح مشروع أو تبديل conversation؛ تحقق من PID/ExecStart/boot/recovery على TEST دون تعديل خدمة مشتركة.
- استعمل Native API ومخزن OpenCode وقاعدة جلساته/Cache الأصليين؛ **لا** قراءة/تعديل SQLite/cache files من Gateway ولا قاعدة Models/Providers مستقلة في PostgreSQL ولا Python discovery engine.
- تحديث فهرس OpenCode الأصلي عبر `models --refresh` المجدول داخل maintenance القائم كل 7 أيام افتراضيًا أو 14 يومًا، وزر إداري يدوي. الاستخدام يكون بنفس حساب OpenCode/HOME/XDG الموثق، بعملية CLI صيانة قصيرة وليس daemon جديدًا.
- تجربة 1.19.4 المؤرخة أثبتت أن CLI يحدّث cache المخزن، لكن خدمة serve الجارية قد تبقى على snapshot أقدم؛ **لا تعد تحديثًا فوريًا في الواجهة ولا تعيد تشغيل OpenCode أو dispose للجلسات لفرضه**. فشل التحديث يجب ألا يمس آخر cache صالح.
- SSE هو المصدر الأساسي لحالة الرد؛ coalesced history وincremental DOM دون تحميل `/message` عند كل حدث. قِس وقت أول نص وعدد الاستدعاءات قبل ادعاء تسارع.

## 6. حالة GitHub المؤكدة — مصدر لا يساوي نشر
- أحدث رأس مصدر مؤكد في تقرير العمل: `3b1d184078b3657d190e3175ce356bb529c4b45f`، منجز Shell/Connections في `1c7deafe04a8260f7ec9c4e8d171ed5dafc142f6`، ومتابعة التوثيق تالية له. تحقق من HEAD مجددًا عند الاستئناف.
- منجز في المصدر مع اختبارات محلية: Native SSE/chat/drafts/Todo/agent-model-variant/permissions/abort، وإزالة اختبار single owner، مزوّدون 50 + بحث يدوي، ملكية ملفات ومفاتيح عبر Gateway، منع Shell حتى للمدير مؤقتًا، cache refresh الأصلي. فحوص آخر دفعة: 59 Backend و50 UI و6 سيناريوهات Native 1.19.4 محلية. **ليست اختبارات TEST المنشور.**
- لقطة المتصفح أظهرت رسائل `Shared native execution is limited to the TEST owner` و`Use the authorized native TEST transport; per-workspace engines are disabled`، مما يرجّح وجود Backend قديم/استدعاء Legacy في النشر. لا تفتح القيد في الخدمة كحل مؤقت؛ انشر الكود المتوافق كاملًا ثم تحقق.
- لم يثبت نشر الإصدار الأخير على TEST أو تسجيل الدخول بحساب TEST جديد، أو تشغيل OAuth/GitHub الحقيقيين أو اختبار مستخدمين/نموذج مدفوع، ولا boot/ PID المستمر على VPS.

## 7. النشر — الفروقات والاستثناءات الخطرة
**هناك مساران مختلفان؛ لا تعتبر أحدهما بديلًا عن الآخر:**

**أ. Workflow** `.github/workflows/deploy-updates-test.yml` — يدوي `promote-test`، بيئة `test`، فرع `updates`، ينقل فقط `management.js`, `dashboards.js`, `index.html`. **لا** ينقل Backend أو `native-session-client.js` أو `runtime-client.js` أو policy أو auth أو Nginx أو systemd. حاليًا مراجع SSH في الملف تستخدم `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_PRIVATE_KEY`, `STAGING_SSH_KNOWN_HOSTS`، بينما `PORT` ما زال `TEST_VPS_SSH_PORT` مع fallback 22. تأكد أن STAGING تشاور TEST فقط، وأن PORT صحيح؛ لا تستخدم VPS_* الخاصة بنشر LIVE. إصلاح المراجع موثق في commit `1063ffe6d7b2eb1eebd11401f92562b41ae00fb6`. تشغيل 40182585627 فشل قبل رفع الملفات لأن أسماء TEST_VPS القديمة كانت فارغة؛ لا تعتبر الفشل دليلًا على مفاتيح ناقصة أو نجاح نشر لاحق.

**ب. أداة TEST coordinated release** `scripts/native_test_release.py` — هي مسار الحزمة المترابطة، حاليًا **18 ملفًا** وليس 8 أو 12 أو 15. القائمة الحالية حرفيًا:

```
app.js
dashboards.js
runtime-client.js
native-session-client.js
backend/app/main.py
backend/app/routes/native_sessions.py
backend/app/routes/agent.py
backend/app/services/opencode.py
management.js
backend/app/routes/workspaces.py
backend/app/services/native_provider_accounts.py
backend/app/services/github.py
backend/app/routes/admin.py
backend/app/services/native_catalog_maintenance.py
enhancements.js
backend/app/services/policy.py
backend/app/services/providers.py
backend/app/services/workspaces.py
```

- `index.html` **ليس** ضمن الـ18 ويُحفظ دون تبديل، ولذلك تحقق من توافق تضمين السكربتات الحالية ونسخ assets قبل النشر. وكذلك `backend/app/config.py`, `backend/requirements.txt`, ملفات `.env` والـDB وWorkspaces وملفات الاعتماد وخدمة OpenCode **محمية من الكتابة**. بقية ملفات التطبيق غير المدرجة لا تُحدّث بواسطة هذه الأداة؛ إن كانت هناك اعتماديات جديدة خارج القائمة، يجب مراجعتها وإدراجها صراحة في إصدار منسق لا توزيعها عبر UI-only workflow.
- الأداة تفحص تطابق bytes مع baselines معتمدة وترفض تعديلات TEST غير المعروفة، أو Nginx Native routes/config موجودة سابقًا دون reconciliation. لا تعالج ذلك بحذف إعدادات Native الموجودة أو `git reset --hard` أو تعطيل الفحص.
- تعديلات Nginx المتصلة بـTEST قد تتطلب `nginx -t` ثم reload للخدمة المشتركة؛ **لا تفعل هذا دون إثبات أن ملفات ومنافذ LIVE لن تتأثر**. أداة التنسيق قد توقف/تعيد تشغيل `opencode-gateway-test.service` فقط، ولا ينبغي مطلقًا إعادة تشغيل `opencode-native-test.service` أو تغيير محرك OpenCode المشترك. راجع التنفيذ على VPS قبل أي عمل.
- خطّة apply/activate/rollback في توثيق 22 أكتوبر تذكر `--owner-id` و8 ملفات؛ هذه **تاريخية منسوخة**. الصيغة الحالية تستخدم `activate --plan` بلا owner-id؛ لا تنفذ أوامر قديمة.
- الأداة تفترض systemd Gateway TEST يعمل تحت `tahir` في `$APP/backend` وعلى port8001؛ راجع الافتراضات في `inspect` ولا تخترع بديلًا.
- **الإجراء التالي الإلزامي:** قراءة فقط `inspect` باستخدام SHA محدد وتقرير hashes/redacted routes/flags، ثم توفيق config الموجود ومسارات Nginx والتغييرات المحلية مع أداة التحديث **من دون تعديل المحرك المشترك**، والنسخ الاحتياطي لأصول TEST، ثم نشر متناسق كامل، واختبار حقيقي. لا تشغّل Workflow الثلاثة ملفات بمعزل عن بقية الحزمة.

## 8. شروط قبول TEST النهائي
- دخول مستخدم TEST أصلي وتسجيل حساب جديد بطريقة صحيحة، Project/Workspace جديدان، استرجاع مشروع قديم، جلسة Native وإنشاء محادثة، prompt واقعي وSSE سريع ومتواصل وإعادة الاتصال دون فقد الرسالة، models/agents/variants/Todo/questions/approvals/abort.
- Connection catalog ≤50 + manual provider خارج الخمسين + عرض موديل متصل واختباره بمفتاح مخول؛ تفريق catalog عن connected عن tested؛ عدم التسرب بين حسابين ولا session ID/permission/SSE/credentials.
- Shell مرفوض للمستخدم العادي والـsubagents والبدائل؛ المدير يبقى blocked لحين حصر OS داخل مشروعه، ويجب إظهاره كـBLOCKED لمطلب امتيازه لا PASS كامل. ملفات المستخدم الآخر والروابط الرمزية ومسارات الإعدادات غير متاحة لأدوات التنفيذ.
- تحقق persistent native MainPID/service/network، وعدم توليد OpenCode process لكل Workspace، ومقارنة timestamps/calls للكشف عن حمل catalog غير ضروري؛ OAuth/GitHub حقيقيان عند توفر الاتصال. سجّل PASS/FAIL/BLOCKED مع دليل منفصل لكل فئة، ولا تخلط تجربة محلية بنشر فعلي.
- لا تسمح لمستخدم خارجي قبل استكمال تدقيق credential same-provider/OS/filesystem/secrets/authorization. المشروع prelaunch ولا يحتاج تشغيل LIVE.

## 9. ترتيب العمل القادم دون إعادة تنفيذ مهام A–G
1. اقرأ هذا المرجع والـHEAD ومذكرات GitHub الحالية؛ افحص فقط ما تغير منذ آخر تقرير.
2. أثبت مصدر عطل TEST الحالي وأجرِ `inspect` آمنًا لمواقع الملفات وNginx/Gateway، وحدد protected/excluded/dependencies.
3. أصلح **آلية التوفيق للنشر** والتوافق مع installed TEST routes، وليس محرك AI أو وظائف نُفذت سابقًا؛ أجرِ نشر الحزمة الكاملة المنسق من دون المساس بالمشترك مع LIVE.
4. اختبر TEST في المتصفح على مستخدم جديد وبيانات مصرح بها؛ عالج الفشل الحقيقي فقط، مع الحفاظ على Shell ban وملكية الاتصالات.
5. سجل ما بقي مفتوحًا بوضوح: manager Shell sandbox، نفس provider بمفتاحين لمستخدمين مختلفين، Native catalog live reload، OAuth/GitHub الحقيقي، العزل قبل الإطلاق، وأي أثر لاختلاف files/DB/service.
6. حدد SHA منشورًا وhashes للأصول الفعلية ونسخة تراجع، ولا تعتبر push أو 200 لصفحة HTML دليلًا على قبول التشغيل.

## 10. الحماية والتراجع
- لا reset، لا حذف/migrations للـDB، لا مساس بـ`.env` أو `auth.json` أو Cache أو مشاريع المستخدمين، لا اعتماديات أو systemd جديدة، لا نسخ مفاتيح خارج مخزن المستخدم الآمن، ولا تغيير منافذ OpenCode المشتركة.
- backup preimages دقيقة لـTEST قبل أي استبدال، تراجع عن الملفات/إعدادات TEST فقط، وعدم إزالة جلسات Native التي أنشئت بعد التحديث.
- لا تُدخل إعدادات مجهولة في اسم STAGING دون التحقق أنها لا توجه إلى LIVE؛ لا تعرض قيمة Secret أو سجل Environment في المراسلات.

## 11. مصادر الحقيقة والأرشيف
- الأقسام التاريخية المنقولة من v3.5 هي سجل قرارات المالك في تاريخها وليست نسخًا تعليمية سارية مستقلة؛ هذه الوثيقة V3.8 هي المرجع التنفيذي الوحيد. المصدر الجاري في `updates` ووضع TEST الحقيقي هما مرجع حالة التشغيل عند الاختبار.
- GitHub: `docs/NATIVE_CONNECTIONS_SHELL_ACCEPTANCE.md`, `docs/NATIVE_CATALOG_MAINTENANCE.md`, `docs/NATIVE_DEVELOPMENT_1194.md`, `docs/NATIVE_TEST_COORDINATED_RELEASE.md`, `docs/PROJECT_HANDOFF_AND_REMAINING_WORK.md`؛ بعضها يحوي مراحل قديمة يجب تفسيرها تحت override الأحدث.
- ملف `Archive/OPENCODE_GATEWAY_ARCHIVE_V3_3_BEFORE_RECONCILIATION_2026-10-25_AR.md` يحفظ كل نص v3.3، بما فيه جداول المقارنة القديمة والخطة التاريخية واختبارات 1.18؛ لا يتم حذف الأدلة.
- لا تغيّر `master` أو LIVE أو Preview، ولا توجّه Work إلى خطوات نشر إنتاج مستقبلية.


## 12. أحدث فحوص TEST الواقعية وقرار التنفيذ (25 أكتوبر 2026) — يتقدم على افتراضات النشر التاريخية

**حالة البنية:** أكد المالك أن TEST كان يستخدم تثبيت OpenCode مستقلًا، ثم أُلغي وانتقل إلى استخدام تثبيت OpenCode المشترك مع LIVE؛ بقي Python Gateway/DB ومسار التطبيق TEST مستقلًا. عدم وجود بعض المسارات في توجيه TEST الحالي ليس دليلًا على وجوب إعادة تثبيت محرك Native أو إحياء التثبيت القديم. **النسخة 1.19.4 سبق ترقيتها واختبار توافق API الأساسي في التجارب المحلية**؛ لا ترقِّ المحرك ولا تغيّر عملية التشغيل/المنافذ/الـHOME/XDG المشتركة. لا تفترض من اشتراك التثبيت وحده اشتراك PID دون جرد read-only.

**أدلة مأخوذة من Terminal على VPS:**
- `git fetch origin updates` أعاد HEAD `9055cff33b6aa56a41a4b9ed1a2bff3ad560838b` وقت التحضير. Commit `9055cff` غيّر Workflow إلى **Audit-only**؛ ليس Workflow نشر ولم يتسبب في تفعيل تطبيق TEST.
- `systemctl is-active opencode-gateway-test.service` = `active`؛ و`opencode-native-test.service` = `active` في الفحوص المنشورة.
- فحص `scripts/native_test_release.py inspect` السابق على revision `1063ffe6...` أظهر Native feature enabled وحزمة 18 مسارًا؛ `native_sessions.py` ما زال baseline قديمًا، و`native_provider_accounts.py` و`native_catalog_maintenance.py` غير موجودين، وأكد أن إعدادات Nginx/feature/drop-in **موجودة أصلًا**. أداة النشر القديمة ترفضها كـfirst-install configuration، ولا يصح حذفها أو إعادة إنشائها عشوائيًا.
- التوجيه المحلي الموثق في `/etc/nginx/conf.d/opencode-native-test-session-local.conf` يستمع `127.0.0.1:18098` ويحيل `/session`, `/session/`, `/event`, و`permission|question` إلى `127.0.0.2:4097` مع Authorization داخلي، ويعيد 404 افتراضيًا للبقية. الفحص غير الموثّق بالمصادقة أعاد: `/session/status` **200**؛ `/path`, `/provider/auth`, `/experimental/tool/ids`, `/skill`, `/global/health` **404**. الاستدعاء مباشرةً إلى `127.0.0.2:4097/path` أعاد **401 دون مصادقة**، وهو دليل على حماية Native وليس إثبات استجابة JSON مصدّقة. لا تفسّر 404 في Nginx كغياب API من محرك 1.19.4.
- ملف GitHub `backend/app/routes/native_sessions.py` يستخدم أصلًا `metadata('GET','/path',root)` للتحقق من worktree والمسارات النسبية في الموافقات على ملفات المستخدم، ويستخدم `/experimental/tool/ids`, `/global/health`, `/skill` وغيرها لحوكمة الأدوات/metadata. الإصدارات الحالية **غير متوافقة بشكل مكتمل** مع allowlist Nginx المذكورة. لا تلغِ هذه الفحوص أو توسّع الوصول إلى OpenCode raw للعامة.
- بأمر Terminal أُعدّت **14 من 18 ملفًا** مختلفة أو مفقودة محليًا تحت `/home/tahir/opencode-test-diff.bZc6lgFI/new/`، وبصماتها مشتقة من `9055cff...`. الحزمة تتضمن `changed-files.txt` ونسخ preimage للملفات الموجودة في `backup/`. الفحص اللاحق أكد عدد14 ووجود ملفات التحضير، وتطابق preimages مع TEST الحالي وقت الفحص وصحة صياغة Python AST. **لم يحدث أي نسخ إلى ملفات التشغيل، ولا Restart أو Deploy**؛ هذه ليست Backup كاملة للـDB/Nginx/Shared Native. حافظ على المرحلة ولا تخلطها مع نشر ناجح.
- أمر preflight لتحديث التطبيق توقف عن قصد عند `/path => HTTP 404`، ولم يستبدل الملفات. ظهور `logout` جاء بعد `set -e` وانتهاء أمر SSH وليس فشل خدمة OpenCode.

**قرار المالك النهائي — لا تعطيل غير مبرر للإصلاحات اللازمة:** الهدف أن **يعمل النظام بصورة صحيحة لجميع المستخدمين المؤهلين**. يُسمح بتنفيذ أصغر تعديل لازم ومثبت للتوافق، بما في ذلك تحديث allowlist Nginx **الداخلي الخاص بـTEST** عند الحاجة الفعلية، بعد فحص المسارات كلها دفعة واحدة وإثبات وجود نفس مصادقة Basic الخاصة بالخادم، وعدم جعل المسار عامًا، ونسخ preimage واختبار `nginx -t` وخطة rollback. لا تغيّر Nginx العام أو إعدادات LIVE أو IP/ports، ولا تلمس تشغيل أو تثبيت OpenCode المشترك. أي reload لـNginx المشترك يحتاج إثبات أن تغيّر الإعداد يقتصر على TEST وأن فحص التهيئة ينجح.

**خطّة تنفيذ حتمية لا تكرّر الفحص:**
1. اعتمد أدلة VPS أعلاه؛ لا تعِد أوامر `inspect` كاملة بلا تغيير مصدر/حالة. راجع فقط النقاط غير المحسومة: قائمة metadata/auth routes المطلوبة بالفعل وطرق HTTP والسلوك الآمن، ومسار التفويض المحمي، وكون `STAGING_*` يؤدي إلى TEST لا LIVE.
2. عالج تعارض allowlist الداخلي بحده الأدنى **دون إزالة Gateway ownership checks أو Shell deny**؛ لا تضف raw public location ولا Basic إلى المتصفح؛ عند الحاجة اختبر loopback موثّقًا داخل الخادم دون طباعة قيمة السر.
3. تحقق من اختلافات الملفات الـ18 واعتماديات HTML/Config خارج manifest؛ راجع حماية الملفات الأصلية وعدم تغيّرها منذ staging، واحفظ snapshot منظّمًا من **TEST فقط** ونسخة DB TEST آمنة عند التخطيط للنشر. لا تضمّن cache أو Native global credentials المشتركة في rollback آلي.
4. نسق نسخ الملفات الـ14 اللازمة فقط دفعة واحدة بدون `git reset --hard` أو حذف واسع، مع إيقاف/بدء **Gateway TEST فقط إذا احتاج تبديل Backend**. تراجع على أساس البصمات عند الفشل؛ لا تعدّل OpenCode Native service.
5. اختبر مسار مستخدم جديد وحساب ثانٍ مختلف: التسجيل وتسجيل الدخول، إنشاء Project وWorkspace، جلسة Native/PROMPT وSSE، النماذج المتاحة/اتصال الحساب، الملفات والموافقات، رفض الوصول للمشروع الأجنبي، Shell deny، ثم سجّل PASS/FAIL/BLOCKED بدليل. لا تعتبر الحساب التجريبي الواحد سياسة مستخدمين.

**قيد معماري غير محسوم لا يجوز إخفاؤه:** Native `/auth/{provider}` في الخدمة المشتركة عملية-global، ولذلك مفاتيح منفصلة للمزوّد نفسه عبر حسابين لا تعمل بعد بصورة آمنة؛ يجب إبقاء منع الاستيلاء على مفتاح الغير، والسعي إلى طريقة مدعومة لعزل الاعتماد دون محرك لكل مستخدم. فشل هذا الاختبار لا يبرر منع جميع المستخدمين من إنشاء المشاريع أو إتاحة OpenCode الخام بلا Gateway. كذلك Shell لمدير المشروع ما زال متوقفًا إلى أن يتحقق عزله على مستوى OS؛ لا تمنحه دورًا زائفًا ولا تفتح Shell لجميع المستخدمين.

**تمييز صلاحية الخدمة عن الإطلاق العام:** «متاح للجميع» = لا owner-only gate، وكل حساب مصادق عليه ومخوّل يستطيع استخدام مشاريعه طبقًا لصلاحياته وخطته، وليس إتاحة جلسات/أسرار مستخدم آخر أو منح صلاحية غير مقيدة. التسويق/الفتح العام للمنصة ينتظر اختبارات العزل الحرجة، لكنه لا يغير الهدف متعدد المستخدمين ولا يسمح بالعودة لقيد مستخدم واحد.


## تحديث تشغيلي v3.6 — 25 أكتوبر 2026: نشر TEST الفعلي ومشكلة كتالوج المزوّدين

**معلومة مثبتة من طرفية VPS:** نجح نشر ملفات الـDiff الأربعة عشر من حزمة المراجعة `9055cff33b6aa56a41a4b9ed1a2bff3ad560838b`. الرسالة: `TEST_DEPLOY_SUCCESS 14 files; Gateway active; Native PID unchanged`. هذا يلغي وصف «لم تُنشر» الوارد في السجل التاريخي أعلاه؛ لا تعِد نشر الحزمة القديمة. ملف Nginx المحلي تم تحديثه ليمرر metadata اللازمة بأمان، بعد انتظار عامل Nginx الجديد؛ `/path` أعاد 200، ومحرك Native المشترك لم يُعَد تشغيله. ليست نتيجة قبول وظيفي شامل.

**دليل الفحص الذي لا ينبغي تكراره إلا إذا تغيّر التكوين:** استجابة HTTP 200 وJSON للمسارات `/path` و`/session` و`/session/status` و`/permission` و`/question` و`/experimental/tool/ids` و`/global/health` و`/skill` على `127.0.0.1:18098`، وللمسارين `/provider` و`/agent` على `127.0.0.1:18097`، باستعمال directory التطبيق المرجعي (وليس كل Workspace). Nginx يستمع على 18098 والعامل يتجدد مع reload. أي اختبار Workspace يحتاج مجلده الحقيقي.

**دليل من سجل Gateway عند 12:25–12:27 UTC:** إنشاء مشروع جديد `POST /api/projects` أعاد 201؛ إنشاء جلسة Native جديدة أعاد 200؛ قراءة الرسائل/Todo/Events لبعض الجلسات أعادت 200. لكن `/native-session/{workspace}/provider` أعاد 502، وإحدى الجلسات القديمة أعادت 502، وبعض Workspaces القديمة أعادت 409. الـ409 يحتاج تفسيرًا مستقلاً، ولا يعني جواز تعطيل حدود الملكية أو سلامة الملفات.

**السبب المؤكد للـ502 الخاص بالاكتشاف:** استجابة Native `/provider` الصالحة JSON حجمها **7,111,446 بايت**، بينما `backend/app/routes/native_sessions.py:metadata` كان يقيد كل استجابة بـ4 MiB؛ يرفض الكتالوج قبل تصفية الواجهة. أُضيف على `updates` تعديل يسمح حتى **16 MiB لطلب `/provider` فقط** مع الحفاظ على 4 MiB لبقية metadata (`aa5bef6...`). وهذا ليس بديلًا عن التحكم بحجم العرض؛ المطلوب **50 مزوّدًا مع أولوية المتصلين**، بدل ~220 أو أكثر بالواجهة السابقة؛ أُضيف هذا إلى `native_provider_accounts.catalog` على `updates` (`38d90a7...`). التعديلان على GitHub لا يعنيان أنهما نُشرا أو اختُبرا على TEST بعد. التفويض بـ `require_model` يجب أن يبقى مبنيًا على كتالوج Native الأصلي دون الاقتصار على أول 50 مع منع مفاتيح الغير.

**حالة Workflow:** نجح audit عبر SSH. فشل مسار deploy الأول لأن `sudo -n python3` يتطلب كلمة مرور. `sudo -l` أثبت أن الأمر غير التفاعلي المتاح هو إعادة تشغيل `opencode-gateway-test.service`، بالإضافة إلى أداة قديمة `/usr/local/sbin/opencode-test-deploy` التي تستدعي `fresh_test_install.py` من `/home/tahir/opencode-gateway-v2-source` وتستخدم `/etc/opencode-gateway-test-v2.env` و`/opt/opencode-fresh/server.env`. **لا تُستخدم هذه الأداة لتحديث TEST الحالي**. استبدل Workflow بتنزيل مباشر من GitHub `updates` وتطبيق فرق الملفات ضمن حزمة التشغيل المعتمدة فقط باستخدام حساب `tahir` ونسخ preimage، ثم إعادة تشغيل Gateway TEST بالصلاحية الموجودة، دون طلب root لسكربت قابل للتعديل.

**حدود التغييرات التي أكدها صاحب المشروع:** كل ملفات تطبيق TEST المشمولة بالإصدار يمكن تحديثها عند الحاجة (وليس 14 فقط إلى الأبد)، مع backup/rollback للملفات التي تتغير؛ الاستثناءات المحمية من أي تنظيف/نشر افتراضي هي `.env` وملفات الأسرار وقاعدة البيانات وإعدادات النظام وملفات/خدمة/عملية OpenCode المشتركة، وكذلك LIVE و`master`. تخلص من اعتماد v2 المهجور بعد التحقق من عدم استعماله؛ **لا تحذف** `/opt/opencode-fresh/server.env` أو أي secrets/config لمجرد ظهور v2 في اسمه، ولا تعدّل أداة v2 المخزّنة على الخادم دون معرفة تبعياتها. الحذف الفعلي يحتاج فحص مراجع الخدمة ومسار التثبيت وإثبات أنه مهجور؛ التراجع الخاص بملفات التطبيق لا يسترجع حذف secrets أو بيانات.

**القبول المتبقي:** نجاح GET `/native-session/.../provider` مع حد 50 في الواجهة؛ تحميل محادثة موجودة؛ سجل `409` للـWorkspaces القديمة؛ اختبار حسابين مستقلين لإنشاء Project/Workspace وبدء جلسة ونماذج وملفات، والحفاظ على Shell deny وملكية جلسات/مفاتيح كل مستخدم. لا تخلط بين نجاح النظام وعرض نماذج من كتالوج كامل وبين ملكية credentials المعزولة، خصوصًا قيد Native process-global للمزوّد نفسه.


## سجل فحوص VPS المنفذة — تحديث v3.7 بتاريخ 25 أكتوبر 2026 (مرجع منع تكرار الفحوص)

هذا القسم يوثّق **المشاهَد فعليًا** من أوامر المستخدم وسجلات GitHub؛ الأجزاء التاريخية أعلاه لا تُستخدم لاستنتاج أن النشر ما زال معلقًا بعد توثيق النجاح أدناه. لا تكرر هذه الفحوص إلا إذا تغيرت الخدمة أو ملف التكوين أو شيفرة المسار المعني.

| المجال/الفحص | النتيجة المثبتة | القرار أو الدلالة |
|---|---|---|
| GitHub `origin/updates` وقت staging | `9055cff33b6aa56a41a4b9ed1a2bff3ad560838b` | حزمة الـ14 التي نُشرت أولًا مشتقة من هذا SHA؛ ليس هو آخر HEAD. |
| مرحلة التحضير | 14 ملفًا مختلفًا من 18؛ `changed-files.txt` = 14؛ مصدر الملفات موجود؛ AST Python ناجح؛ الملفات الأصلية لم تتغير وقت الفحص | لا تعِد تحضير هذه الحزمة أو الفحص القديم بعد نجاح النشر. |
| ملكية ملفات التطبيق | المجلد `/home/tahir/opencode-gateway-test` والمجلد `backend` = `tahir:tahir` بصلاحية 775؛ `app.js` = `tahir:tahir` 664 | تعديل ملفات TEST نفسها لا يتطلب root؛ إعادة تشغيل Gateway TEST مسموح بـsudo المحدود. |
| خدمة TEST | `opencode-gateway-test.service` تعمل بـ`User=tahir`, `Group=tahir`, `WorkingDirectory=/home/tahir/opencode-gateway-test/backend`؛ Native TEST = active | لا تغيّر user أو WorkingDirectory ولا تعِد تشغيل المحرك المشترك. |
| SHA ملف Nginx القديم | `/etc/nginx/conf.d/opencode-native-test-session-local.conf` له SHA256 `972fa6a13833db26d0f972afe0fc7538656e4c5aad27cee9e9632a250eaf9a11` قبل التصحيح، owner root:root mode 600 | هذه بصمة **ما قبل إصلاح Nginx** ولا يجوز توقعها بعد النشر الناجح. |
| توجيه Nginx القديم | `127.0.0.1:18098`؛ `/session/status` 200 لكن `/path` و`/provider/auth` و`/experimental/tool/ids` و`/skill` و`/global/health` كانت 404 | كانت مشكلة allowlist، وليست حذف API من OpenCode. |
| Native المباشر بالمصادقة | `127.0.0.2:4097/path?directory=...` = 200، `application/json`؛ دون مصادقة سابقًا 401 | المحرك يوفّر `/path` ويجب الحفاظ على Basic الداخلي وعدم عرضه للجمهور. |
| Nginx المستمع | `ss` أظهر `nginx` يستمع 127.0.0.1:18098؛ master PID 131186 وقت الفحص؛ عامل PID 349571؛ ملف إعداد TEST موجود بالفعل بين ملفات `nginx -T` | لا يوجد مستمع بديل على هذا المنفذ. قيم PID تاريخية لا تفرض بقائها. |
| Reload | `nginx -t` ناجح، systemd سجّل Reloaded بنجاح؛ عمليات Worker تتغير بعد reload | الاستجابة الفورية قبل تبدل worker قد تأتي من التكوين السابق. |
| تجربة `/path` المؤقتة بلا انتظار | HTTP 404، ترويسة التشخيص `X-Test-Path-Probe` غائبة؛ أُعيد ملف الإعداد القديم | الاختبار لا يثبت مشكلة Host أو محرك؛ كان worker القديم يخدم الطلب. |
| تجربة `/path` بعد انتظار worker | HTTP 200، `ROUTE MATCHED: MATCHED`, `WORKERS CHANGED: True` ثم استُعيد الإعداد القديم بعد الاختبار | **حُسم السبب**: يجب التحقق بعد تبدل workers، لا إعادة فحص نفس المشكلة. |
| احتمال proxy بيئة Python | `DEFAULT HTTP 200` و`NO_PROXY HTTP 200` على `/session/status` | لا دليل على أن Proxy بيئة Python كان سبب 404. |
| `sudo -l` | root ALL بكلمة مرور؛ NOPASSWD لـ`systemctl restart opencode-gateway-test.service`، و`/usr/local/sbin/opencode-test-deploy` بلا args | CI لا يستدعي `sudo -n python3`؛ استخدم أذونات restart الموجودة فقط. |
| أداة نشر v2 | `/usr/local/sbin/opencode-test-deploy` root:root 700؛ تشير إلى `/home/tahir/opencode-gateway-v2-source`, `/etc/opencode-gateway-test-v2.env`, `/opt/opencode-fresh/server.env` وتستدعي `fresh_test_install.py install` | **لا تستخدمها** لنشر Gateway TEST الحالي؛ لا تحذف env أو engine shared دون إثبات عدم الاستخدام. بحث systemd/nginx عن هذه المراجع لم يعرض نتائج، لكنه لا يثبت عدم اعتماد كل خدمة أخرى عليها. |
| النشر الأول من Terminal | `TEST_DEPLOY_SUCCESS 14 files; Gateway active; Native PID unchanged`; التوجيه الداخلي `/path` أعاد 200 بعد worker refresh | **نشر ناجح**؛ لا تعِد نشر هذه الـ14 بالطريقة اليدوية. |
| فحص Metadata العام بعد النشر | 10/10 endpoints أعادت `HTTP 200 application/json`: على 18098 `/path`, `/session`, `/session/status`, `/permission`, `/question`, `/experimental/tool/ids`, `/global/health`, `/skill`؛ وعلى 18097 `/provider`, `/agent` | يعكس route reachability لدليل اختبار التطبيق؛ لا يثبت شكل كل استجابة لمجلد Workspace أو نجاح authorization. |
| جلسة المستخدم الفعلية من سجل 12:25–12:27 UTC | `POST /api/projects` = 201؛ إنشاء Native session = 200؛ message/todo/event = 200؛ provider discovery = 502؛ جلسة أقدم = 502؛ بعض workspaces = 409 | وظائف متفرقة نجحت؛ مشكلات الجلسات القديمة و409 تبقى غير محسومة، ولا يجب تجاوز الأمان لأجلها. |
| السبب المقاس لكتالوج `/provider` | response صحيح JSON بحجم `7,111,446` bytes، أكبر من الحد 4 MiB | فشل كود Gateway قبل عرض الكتالوج؛ لا علاقة له بالـ50 مزودًا المعروضين بحد ذاته. |
| إصلاح GitHub للكود | `aa5bef6…` يرفع حد **القراءة فقط لـ`/provider`** إلى 16 MiB؛ `38d90a7…` يقيد واجهة الكتالوج إلى **50 provider** مع أولوية المتصلين؛ لا يغير تفويض model من المصدر الأصلي | حافظ على أمان Account ownership وحماية مفاتيح الحسابات؛ لا تعد إلى 220 مزودًا في الواجهة. |
| نشر GitHub المباشر بعد الإصلاح | GitHub Actions run **40193999369** نجح بتاريخ 25 أكتوبر: `UPDATED backend/app/routes/native_sessions.py` و`UPDATED backend/app/services/native_provider_accounts.py` ثم `TEST_DIFF_DEPLOY_SUCCESS 2 revision 8e2a5c60af40f86c6888a4806922c0a537dfb6d2`؛ CI validation run **40193999382** نجح | **التصحيحان نُشرا بنجاح على TEST**؛ يلزم اختبار وظيفي جديد لكتالوج المستخدم لأن نجاح الخدمة وحده لا يثبت اختفاء جميع أخطاء 502. |
| حالة Workflow بعد النشر | commit `e41afab42975ce3b5e411a10632e6f120cee8222` عطّل trigger التلقائي `push` بعد نجاح One-shot، وترك `workflow_dispatch` يدويًا على `updates` فقط | أسرار SSH محفوظة في GitHub Secrets، غير مطبوعة؛ لا يمكن حذف قيمتها ثم إعادة إنشائها لاحقًا دون امتلاك الأصل. لا تشغّل النشر تلقائيًا دون قصد. |

**حدود حماية المالك:** لا تستبدل أو تحذف `.env` أو قواعد البيانات أو إعدادات النظام أو تثبيت OpenCode المشترك أو ملفات الاعتماد والـCache. بقية ملفات تطبيق TEST يمكن تحديثها من GitHub عبر قائمة إصدار معتمدة وإحلال الملفات **المختلفة فقط** ونسخ preimages؛ عبارة «انشر كل شيء» لا تعني overwrite غير معروف أو `git reset --hard`. إعداد Nginx الداخلي الخاص بـTEST تم إصلاحه في النشر الأول؛ لا تعِد كتابته ما لم يتغير الاحتياج.

**المتبقي قبل وصف المشروع جاهزًا للجميع:** أعد فتح UI على TEST بعد GitHub run الناجح للتأكد من عرض 50 مزوّدًا وفتح محادثة جديدة والنماذج المتصلة؛ اختبر جلسة قديمة فاشلة بصورة منفصلة؛ حل 409 لمجلدات Workspace القديمة دون تعطيل فحوص ملكية ومسارات المشروع؛ تحقق من مستخدمين مستقلين وعزل المشاريع والجلسات والمفاتيح؛ لا تفتح Shell ولا ترفع قيد Single Native provider slot للمزوّد نفسه قبل حل آمن. لم يثبت أي من هذه الاختبارات بمجرد run أخضر.


---

## 13. القرارات المحدثة والملزمة 27 أكتوبر 2026 — الأولوية الأعلى عند التعارض

**قاعدة النسخة الواحدة:** هذه المذكرة V3.9 هي المصدر التنفيذي الوحيد لجميع توجيهات Work القادمة. الأقسام 1–12 تحافظ على الأدلة والقرارات التاريخية؛ أي صياغة تاريخية عن حالة نشر أو عائق وقتي تُقرأ بحسب تاريخها، ولا تنسخ كتعليمات جديدة. لا تُنشأ مذكرات موازية بعد اليوم؛ كل تغيير يُضاف هنا بقسم مؤرخ وتحديث رقم الإصدار. الأرشيف للاطلاع فقط وليس للمقارنة اليومية.

### 13.1 Security + Performance: تحسين صغير، لا إعادة بناء
1. **Python/PostgreSQL: Control Plane فقط**: تسجيل الدخول، الحسابات، الاشتراكات، صلاحيات الإدارة، ملكية User→Project→Workspace→Session، ربط بيانات GitHub والمزوّدين، قواعد الوصول والتدقيق. فحص ملكية مستقل عند كل API حساس؛ لا يكفي فحص تسجيل الدخول مرة واحدة.
2. **OpenCode Native 1.19.4: Data/Execution Plane**: جلسات ومحادثات ورسائل ونماذج ووكلاء وملفات Agent وأوامر أدوات مسموحة والبناء وSSE. الطلب والرد عبر Nginx internal redirect بعد تفويض Python، دون Python AI proxy أو queues أو stream processor بديلة؛ لا محرك لكل مستخدم أو Workspace.
3. **تفويض منخفض الحمل**: احذف metadata المكرر غير الضروري من المسار الحرج فقط بعد قياسه. يجوز metadata Native للتحقق من تعيين Session للمجلد أو لتطبيق سياسة أمنية متغيرة؛ لا تُخزَّن نتيجة السماح القديمة لتجاوز سحب صلاحيات المستخدم. لا تزل tool restriction أو file boundary لتسريع الطلب.
4. **عزل فعلي عند التشغيل**: Gateway ownership وحده لا يمنع أداة داخل Native مشترك من قراءة ملفات حساب آخر. طبّق واثبت قيود أدوات Native وحدود OS/filesystem والأسرار ومنع Shell/Command/MCP bypass للمستخدم العادي. امتياز Project Manager لـShell لا يفعّل حتى إثبات OS isolation داخل مشروعه؛ إذا تعذر إثبات ذلك فتبقى القدرة الخطرة معطلة، وتُسجل BLOCKED.
5. **Recover / prompt_async**: إصلاح حالات `uncertain` بحيث يُستخدم messageID لمصالحة طلب ربما استلمه Native، دون إعادة إرسال آلي أو محو مسودة/ملف؛ اختبر Stop, Recover, reconnect وحفظ native history. حالة مرجعية: `testuser` محادثة `New Test File`؛ لا تحذف بياناتها.
6. **Files + quota**: توجد `manager.files()` و`manager.content()` ووظائف Git في Python؛ لا تنقلها بلا قياس وتحقق توافق. يوجد `usage_bytes()` بمسح `rglob('*')` قبل بعض prompt_async؛ قس أثره على المشاريع الكبيرة، وخففه دون تجاوز الحصص أو فتح TOCTOU. حافظ على الوظائف الحالية.
7. **Native catalog cache**: مصدر الحقيقة هو كتالوج OpenCode المحلي/الأصلي؛ تحديث `models --refresh` كل 7 أيام افتراضيًا أو 14 بإعداد المدير، داخل الصيانة الحالية وبهوية HOME/XDG المطابقة. لا CLI refresh لكل login/message ولا daemon إضافي. Cache العرض 30 ثانية لبعض البيانات ليس تحديث كتالوج؛ لا يفترض تحديث snapshot أن Native process reload حصل. الصلاحيات وسحبها فورية ولا تنتظر 7–14 يومًا؛ الرسائل وSSE بيانات حية وليست catalog.
8. **اختبارات قبول**: مستخدمان مختلفان ومشروعان مستقلان، ملفات ومرفقات وسجل جلسات وأحداث SSE وprovider secrets، وNative tool attempts خارج Workspace. اقس زمن التصريح وprompt_async وfirst text وعدد metadata calls ومعدل الأخطاء وCPU/RAM قبل وبعد؛ قدّم PASS/FAIL/BLOCKED بأدلة.

### 13.2 سياسة GitHub للمشاريع الخاصة بالعملاء — عرض ≠ تنزيل
**ما ثبت في `updates` بتاريخ المراجعة:**
- `backend/app/services/github.py:list_repositories` يجلب قائمة المستودعات المسموح بها لـGitHub App installation الخاص بالمستخدم، ولا يستنسخها عند مجرد عرضها. يسرد حتى 100 عنصر بالصفحة ويستخدم pagination؛ يجب التأكد من انتمائها لنفس المستخدم عند كل طلب. مصدر القائمة GitHub لا قاعدة بيانات منسوخة للمشاريع.
- `backend/app/routes/workspaces.py:_github_source` يفحص ربط GitHub والترخيص للمستودع والفرع قبل إنشاء مشروع. لا تعرض مستودعات حساب الإدارة لمستخدم آخر. مجرّد ظهور مستودع في picker لا يعني امتلاكه Workspace أو تنزيله.
- `backend/app/services/workspaces.py:clone_github` يستعمل `--depth 1 --single-branch --no-tags`. إذا أعطى العميل `working_paths` يُستخدم `--no-checkout` ثم `sparse-checkout --cone`; يمكن اختيار عشرة مجلدات نسبية على الأكثر. **إذا تركت `working_paths` فارغة، يقوم Clone افتراضي كامل للفرع المختار**؛ shallow لا يعني تنزيل ملفات قليلة، وsparse-checkout في الحالة الحالية لا يضمن تنزيل blobs المطلوبة فقط.
- `GITHUB_WORKTREE_LIMIT_BYTES = 512 MiB` هو حد لنسخة العمل في منطق الحصة، **وليس دليلًا أن عملية الاستنساخ نفسها لا تستطيع استهلاك شبكة/قرص/ذاكرة أكثر لحظيًا**؛ لا تُعدّه حماية مسبقة كافية دون قياسات وحراسة عند التنفيذ.

**السياسة المطلوبة، دون إضرار بالمستخدمين الحاليين:**
1. **Lazy-by-default**: عرض metadata للمستودعات/الفروع/الأحجام دون clone؛ لا تنشئ أو تنسخ أي مشروع حتى اختيار المستودع والفرع ونطاق العمل صراحة من المستخدم الصحيح.
2. **الاختيار الجزئي أولًا**: عند إنشاء Workspace GitHub جديد، اطلب نطاق ملفات أو مجلدات العمل، أو قدّم خيار «المشروع كامل» موضح التكلفة وحجم التحميل المتوقع. إذا كانت الواجهة لا تدعم ذلك، لا تغير سلوكها بصمت؛ أضف واجهة بسيطة أو gate على المشاريع الكبيرة بعد مراجعة التوافق.
3. **اقتصاد الموارد**: افحص حجم repo وbranch والنطاق المختار قبل الاستنساخ. نفّذ shallow + sparse + partial clone (`--filter=blob:none` أو blob size limit) **فقط** إذا أثبتت اختبارات المستودعات العامة والخاصة وصلاحية fetch عند الطلب أن استخدامها آمن مع بيانات الاعتماد وOpenCode. لا تضمن التقنية الصفرية للتحميل ولا تعممها قبل الاختبار؛ ضع timeout ومساحة قصوى/حد حركة ومسار rollback وتنظيف النسخ الفاشلة المعزولة دون حذف بيانات قائمة.
4. **تعديل صغير دون Clone كامل**: لطلبات تغيير ملفات محدودة جدًا، فضّل مسار GitHub API/commit أو فرع/PR مخصص إن كانت أدوات Work/Codex توفره مع الصلاحيات، بعد قراءة الملفات ذات الصلة فقط. لا تعِد بناء repository محليًا إذا لم تتطلب المهمة build/test محليًا. لا تستخدم تعديل مباشر على main/master لعميل دون موافقة.
5. **عزل العملاء**: ربط GitHub App شخصي؛ validate `installation_id`, `repository_id`, user_id, branch, workspace_id` من جهة الخادم. لا توجد قائمة عامة لمستودعات المستخدمين داخل واجهة عميل آخر، ولا shared credential. منع private repo enumeration والربط غير المشروع وحتى استدعاءات branch/push/sync بعد انتهاء التفويض.
6. **شروط عند الانتهاء**: كل مشروع عميل له branch معزول/PR افتراضي، ومراجعة diff قبل commit/push؛ لا تشغيل dependencies/scripts مجهولة تلقائيًا، ولا build/test إلا بإذن وقيود CPU/RAM/وقت/قرص. لا تبقِ نسخ عمل ضخمة دون سياسة cache/retention مصرح بها تحافظ على الملفات غير المدفوعة والتعديلات غير المرفوعة.
7. **قياس قبول GitHub**: (أ) فتح قائمة المستودعات لا يرفع حجم WORKSPACE storage ولا يبدأ Git clone؛ (ب) محاولة مستخدم B مشاهدة أو نسخ مستودع A تُرفض؛ (ج) مشروع كبير جزئي يُقاس network bytes, disk bytes, time; (د) diff/push مع token المالك فقط؛ (هـ) تأكيد ملفات مستقلة لمستخدمين اثنين؛ (و) الأخطاء تعيد الموارد بلا فقد بيانات.

### 13.3 الفرق بين ChatGPT Work الخارجي وOpenCode Gateway الذي نبنيه
- وفق وثائق OpenAI المنشورة في 27 أكتوبر 2026، اتصال GitHub المدمج في ChatGPT يسترجع محتوى المستودعات المصرّح بها **عند الطلب** دون إنشاء sync index، وهو عادةً **للقراءة**. يرى التطبيق المستودعات التي سمح بها مالك GitHub؛ ظهورها في القائمة لا يعني تنزيل جميع ملفاتها أو منحها لعميل آخر. مراجعة الاختيارات تكون في GitHub App installation / ChatGPT Settings > Plugins > GitHub.
- عمليات التعديل/الفرع/الـPR/الدفع تحتاج قدرة تحرير مخوّلة مثل Codex أو أدوات GitHub المناسبة في Work؛ **لا تعتبر اتصال GitHub للقراءة إذنًا بالكتابة**. قد تتطلب المهمة البرمجية checkout محليًا أو جزئيًا؛ سياسات الاستهلاك الدقيقة تختلف حسب الأداة ولا يجوز ادعاء ضمان عالمي بأنها لا تعمل clone.
- لا تفرض هذه المذكرة تغيير إعدادات منتج ChatGPT Work نفسه؛ هي **سياسة تشغيل لطلباتنا إلى Work** وقيود تعديل كود Gateway.

### 13.4 تنفيذ آمن وتوثيق النسخة الوحيدة
- `diirzoro/codex-opencode-gateway`، فرع `updates` وخادم TEST فقط. لا `master`/LIVE/Preview ولا تغيير native engine أو Nginx/shared service أو HOME/XDG أو ports بلا موافقة مستقلة وضرورة مثبتة.
- ابدأ read-only مقارنة repo وTEST ثم patch صغير وعملية نشر منسقة مع backup/rollback. لا تنسخ مجلدات العميل أو reset DB أو تمس الأسرار. افصل بين: **موجود بالكود** / **مختبر في TEST** / **ناقص**.
- عند وجود أي تعارض بين تعليمات التنفيذ التاريخية والأولويات الحالية، يتقدم قسم 13؛ الحقائق التاريخية لا تُحذف بل تُوسم بحسب تاريخها. التحديث المقبل يتم في **هذا الملف نفسه**، لا في وثيقة ثانية أو رسالة قرارات موازية.


---

## 14. القرار الموحّد الجديد: GitHub Preview وحصص Silver/Gold وخطة نمو العملاء — 27 أكتوبر 2026

**أولوية التعارض:** هذا القسم يكمل القسم 13، ويحل محل أي تعليمات سابقة توحي بمنع دراسة/تحسين Preview على TEST كليًا؛ الممنوع هو تفعيل تنفيذ غير معزول أو تغيير LIVE/Preview الإنتاجية أو الخدمات المشتركة بغير تفويض. لا ينبغي تحويل متطلبات مستقبلية إلى ادعاء بتنفيذ حالي. **مرحلة المشروع الحالية: لا عملاء فعليين بعد؛ الإطلاق وتوسيع البنية مستقبلان.** لا شراء VPS أو تشغيل عمال إضافيين الآن لمجرد تخطيط المنتج.

### 14.1 سلوك GitHub المطلوب
1. عرض المستودعات والفروع المصرح بها يكون **Metadata فقط** دون تنزيل؛ الاتصال بحساب GitHub وإظهار الملفات لا يُنشئ تلقائيًا Workspace أو Clone. الفصل بين اتصالات مستخدمي GitHub إلزامي.
2. تعديل الملفات المطلوبة فقط في المرحلة المعتادة، باستخدام الاختيار الجزئي والمصدر الأصلي؛ جلب المزيد عند الحاجة الفعلية للـimports/config/test/build ضمن نفس صلاحيات العميل. لا نضمن أن sparse-checkout يوفّر الشبكة إذا كانت blobs قد سُحبت بالفعل؛ قياس partial clone مطلوب.
3. في كود `updates` محل المراجعة: `--depth 1 --single-branch --no-tags` و`sparse-checkout --cone` عند اختيار `working_paths`؛ تركها فارغة يسمح بـClone الفرع. الحد القديم `GITHUB_WORKTREE_LIMIT_BYTES=512 MiB` **حالة كود** وليس سياسة الاشتراك النهائية. لا تُغيّر هذا الحد تلقائيًا إلى 2 GB دون اختبار المساحة والقياس وضبط عدد المشاريع.
4. لا تستبعد الصور والخطوط المهمة للتطبيق بلا تحقق؛ يمكن تجنب الفيديوهات والأرشيف والنسخ الاحتياطية والملفات غير المرتبطة، مع تحذير عندما تصبح المعاينة ناقصة بسبب أصل مستبعد. منع `node_modules` وBuild artifacts غير الضرورية من النقل الافتراضي لا يلغي الحاجة لتحضير التبعيات في بيئة معزولة.
5. التعديل على فرع منفصل ومراجعة Diff/PR قبل Push/Merge. لا إعادة كتابة قاعدة العملاء ولا تشغيل سكربتات مجهولة على Gateway VPS.

### 14.2 معاينة صحيحة للمشاريع دون استنزاف VPS
1. المرجع الوظيفي المعتمد أصلًا `docs/SMART_PREVIEW_POLICY.md`، والسياسة المُلزِمة **تُدمَج مفاهيميًا هنا** دون إنشاء تنفيذ موازٍ. شيفرة `preview.py` تدعم معاينة HTML آمنة للقراءة فقط، وتوجد شاشة Preview. مسار `preview_runner.py` للـbuild/dynamic مربوط بشرط وجود عامل مُهيأ؛ لا يُعَد التشغيل الفعلي لمشاريع React/Next.js/SSR/Python جاهزًا بمجرد وجود API أو شاشة Start/Stop.
2. ثلاث طبقات: (أ) Git Diff ومراجعة الملفات دون تنفيذ، (ب) معاينة ثابتة أو Build محفوظ معزول وفق نوع المشروع، (ج) معاينة ديناميكية قصيرة لمشاريع SSR/backend فقط بعد إثبات Worker isolation. لا تُقدَّم معاينة ثابتة كدليل على صحة Backend أو التكاملات.
3. **بدء صريح فقط** من Start Preview/View Changes، وليس عند Login أو GitHub connection أو فتح Workspace أو تغيّر ملف أو Polling. بعد **300 ثانية من عدم النشاط الحقيقي** يوقف التنفيذ الديناميكي؛ بقاء التبويب مفتوحًا أو polling لا يمدد المؤقت، ولا يُعاد التشغيل دون ضغط المستخدم. النتائج الثابتة المؤقتة يمكن عرضها دون Runner دائم.
4. التحقق الحقيقي قد يحتاج مصادر أكبر من نطاق التعديل فقط: الملفات المصدّرة والمستوردة، manifests وlockfiles وassets الضرورية، ثم dependencies داخل build worker. التوسعة التدريجية آمنة ومحدودة الحجم؛ تجاوز السقف ينتج تحذيرًا واضحًا أو طلب توسعة نطاق، **لا نتيجة نجاح وهمية**.
5. Preview المعزول لا يعمل على العملية الرئيسية لـGateway أو OpenCode، ولا يشغل أوامر عملاء غير موثوقة مباشرة على VPS. مطلوب حدود OS حقيقية للـCPU/RAM/disk/process/time، شبكة خروج مضبوطة، منع الأسرار وبيانات LIVE وخدمات localhost/metadata وملفات المستخدمين الآخرين؛ منفذ معاينة مختلف وauthorization عند كل وصول. إذا لم يتوفر Worker معتمد: تظل static/diff متاحة، والبناء الديناميكي **BLOCKED**، بلا تشغيل بديل غير آمن.
6. احتفظ بنتيجة آخر Build ناجح حسب المستخدم/المشروع/revision مع TTL والحصة؛ إعادة استخدامها لا تعني تجاهل ملفات تغيرت. Preview لا يقوم بCommit/Push/Merge/Deploy أو يغيّر محادثة OpenCode.
7. Preview قبل/بعد يعرض نسختين حقيقيتين حين تتاحان؛ وإلا يظهر Diff ونتائج اختبارات محددة بدل صور متخيلة.

### 14.3 خطة الاشتراكات: مقترح منتج مستقبلي لا ميزة منشورة
| الباقة | سقف نسخة العمل **لكل مشروع** مقترح بعد اعتماد السعة | التوصيف |
| --- | --- | --- |
| Silver / فضية | **800 MB** | تعديل محدد وPreview عند الطلب وفق السعة |
| Gold / ذهبية | **2 GB** | مشاريع أوسع وحجم عمل أكبر وفق السعة |
- القيم المذكورة **سقف لنسخة العمل لكل مشروع، لا ضمان لاستهلاك RAM ولا حجم رفع الملف الفردي ولا عدد مشاريع غير محدود**. يجب الاتفاق لاحقًا على حد إجمالي للحساب، عدد Workspaces النشطة، وسياسة حساب metadata/Git objects/artefacts والـtemporary build، قبل تطبيق الباقات.
- ليست هذه الأرقام إعدادات موجودة أو مُفعّلة: الحد الموجود حاليًا لنسخة العمل GitHub في الكود كان 512 MiB؛ الرفع إلى 800 MB/2 GB يتطلب اختبار حد أثناء Clone وFetch وCheckout وBuild، وليس فحص حجم متأخر فقط.
- تخزين مشاريع ومحادثات غير مدفوعة/غير منشورة لا يُحذف تلقائيًا؛ اقترح سياسة دورة حياة تحفظ التعديلات والمراجع، وقدّم تمييزًا بين التخزين الدائم والمؤقت بعد موافقة لاحقة.
- لا يعني Gold تشغيل SSR أو Shell بلا عزل؛ نفس ضمانات الأمن لكلا الباقتين. خصائص أخرى (عدد المشاريع/الأولوية/الأسعار) **غير متفق عليها** وتظل مؤجلة.

### 14.4 التوسع التجاري وشراء الموارد
- الحالة الراهنة **صفر عملاء**؛ لا توجد حاجة معتمدة لشراء VPS إضافي الآن. القاعدة: الاستخدام المقاس، وليس عدد الحسابات وحده، يحدد سلامة التوسعة.
- يبدأ التخطيط التقني والميزاني قبل بلوغ **50 عميلًا مسجلًا فعليًا**؛ عند **50 عميلًا** تصبح مراجعة ترقية VPS/CPU/RAM/SSD ومسار Preview Worker إلزامية، ويُتخذ قرار الشراء بناءً على القياسات. يجوز الترقية **مبكرًا** عند تشبع RAM/CPU/القرص أو ارتفاع زمن الانتظار أو فشل بناء المعاينة.
- هدف خدمة **100–200 عميل** يتطلب الفصل بين إجمالي حسابات العملاء وعدد العملاء النشطين في اللحظة نفسها. لا تخصص Runtime دائمًا لكل حساب؛ استخدم lazy selective workspaces, source control في GitHub, static artifacts cache, مع حراسة مساحات العمل النشطة وعزل العمال الديناميكيين عند الطلب.
- مثال تخطيطي فقط: 70 فضيًا × 0.8 GB + 30 ذهبيًا × 2 GB = **116 GB** لسقف نسخ عمل مئة مستخدم بمشروع واحد لكل مستخدم يستخدم كامل حصته؛ لا يشمل Git objects الإضافية وBuild/cache والنسخ الاحتياطية والـDB. عند 200 عميل بنفس التوزيع: **232 GB**. هذه **ليست** تقديرات إشغال فعلي أو وعدًا بسعة VPS الحالية.
- سياسة Smart Preview السابقة فيها إرشاد ترقية RAM إلى نحو 16GB ودراسة VPS عامل معاينة منفصل عند ~50 عميل مدفوع أو قبل ذلك إذا ثبت التشبع؛ ليست مواصفة شراء ثابتة ولا أمرًا فوريًا. الموارد النهائية تتحدد بعد benchmark.

### 14.5 المطلوب من Work عند تسلم المذكرة
1. ابدأ **Read-only audit** للمذكرة الموحدة وGitHub `updates` وخادم TEST: جدول **موجود بالكود / منشور TEST / مختبر / غير منفذ / مؤجل** لكل مطلب، واحصر التعارضات **داخل نفس المذكرة**.
2. لا تغير البنية أو تجعل كل سياسة مستقبلية ميزة مفعّلة. عند السماح بالتنفيذ، ابدأ بأصغر إصلاحات Native prompt/recover وحماية المستخدمين وGitHub selective resource limits وStatic Preview الموجودة؛ الامتيازات Silver/Gold لا تُفعّل تجاريًا قبل موافقة مستقلة على الحصص الكلية وسعة التخزين.
3. أثبت بالأرقام قبل/بعد استخدام مساحة/شبكة Clone (شامل بيانات Git وCheckout)، ووقت/ذاكرة Build Preview، ورفض العزل بين حسابين، وإمكانية استعادة رسالة معلقة، دون تغييرات LIVE.
4. الخادم TEST و`updates` فقط؛ لا تثبيت عمال جديدة أو restart native أو Nginx مشترك أو تغييرات secrets/ports/DB دون موافقة منفصلة. احفظ نسخ rollback عند أي إصلاح فعلي، ولا تُحمّل عميلًا أي ملفات غير ضرورية تلقائيًا.
5. **هذه V3.9 هي المذكرة الوحيدة**: لا مذكرات أو تناقضات جديدة. سجلات الإصدارات التاريخية في الأعلى مرجع تدقيقي فحسب؛ القسم 14 يتقدم على أي توجيه Preview أو سعة قديم متعارض.


---

## 15. مصالحة Work والتنفيذ الفعلي — 27 أكتوبر 2026

**المرجع التنفيذي الوحيد:** هذا الملف نفسه. الأقسام السابقة محفوظة للتاريخ؛ عند التعارض يتقدم توضيح المالك الأحدث والقسمان13–14 ثم هذا السجل فيما يتعلق بأدلة التنفيذ. إشارة القسم11 إلى V3.8 تاريخية وليست مرجعًا ثانيًا. لا تتحول عبارة «منفذ» في مذكرة إلى قبول TEST دون دليل.

حُفظ سجل Work السابق كاملًا دون حذف أو إعادة صياغة في [الأرشيف التاريخي](archive/WORK_HANDOFF_THROUGH_20261027.md). حجمه 424833 بايت، SHA256 `0b8baa477fada5546ba3119ca971986e5f297a19a17eb0e506759d53c144f1de`، ومصدره commit `f7719c2f5669d8ae94baec1b97640cfaafb42512`. يشمل الأعمال والاختبارات والعوائق من البداية إلى27أكتوبر؛ لا تستخدم أوامر النشر القديمة أو الموافقات التاريخية على master كإذن حالي. ملف handoff القديم صار مؤشرًا لهذا المرجع فقط.

### 15.1 نطاق المراجعة ودرجات الإثبات

قُرئت المذكرة الأصلية كاملة306أسطر، وقورنت بسجل Work وبفرع `updates` المثبت عند `f7719c2f5669d8ae94baec1b97640cfaafb42512` بعد fetch. روجعت مسارات GitHub، Native authorization/client، الحصص، جدولة الكتالوج، Preview runner والسياسات ذات الصلة. فُتح TEST بالحساب الموجود `testuser · customer` للقراءة؛ استعاد المشروع والمحادثة والنماذج وقائمة Todo. لم تُرسل رسالة أو تُشغَّل معاينة أو تُقرأ ملفات حساسة في هذه المراجعة.

لا اتصال SSH مهيأ في هذه الجلسة. لذلك نسخة Backend المشغلة وsystemd/Native PID وPostgreSQL/migrations والموارد والنسخ الاحتياطية الحالية **غير متحققة مباشرة**؛ لا نكرر فحص البنية القديم، ولا نستنتج هذه الحقائق من HTTP200 أو من source. حالة المحرك المستمر وPID غير المتغير في الأقسام السابقة دليل المالك بتاريخها، لا قياس جديد اليوم.

| المطلب | موجود بالكود | دليل TEST | الحالة الحالية / الباقي |
|---|---|---|---|
| Gateway control plane وNginx Native transport | authentication وملكية project/workspace/session وسياسة الأدوات؛ AI/SSE ليست Python proxy | حساب testuser ومحادثاته استُعيدت؛ Native models وTodo ظاهرة | يعمل لمسار الحساب المختبَر؛ قبول حسابين متزامنين ومحاولات أدوات خارج المجلد غير مكتمل |
| لا single-owner gate | بوابة المالك القديمة غير موجودة؛ القبول بحسب الحساب والملكية | testuser العادي يفتح Workspace | لا يُعاد قيد المالك؛ لا ادعاء قبول جميع الحالات أو خطط العملاء |
| عزل الملفات والأسرار وShell | فحص مسارات/روابط، deny للأوامر/بدائلها/unknown tools/subagents؛ تشديد ملفات محمية في ef5f114 | لم يُختبر التنفيذ الجديد على الخادم | جزئي؛ Shell يبقى ممنوعًا للجميع حتى إثبات OS confinement؛ لا شهادة عزل runtime مشترك |
| prompt_async / Recover / Stop | messageID reconciliation، حفظ المسودة/المرفقات، لا إعادة إرسال آلية؛ abort محدود؛ أولوية terminal SSE على ack متأخر | تاريخ المحادثة المرجعية ظاهر؛ لا reproduction جديد لحالة uncertain | اختبارات VM ناجحة؛ اختبار انقطاع فعلي والتعافي على TEST بهذه النسخة باقٍ |
| الأداء والحصص | request-local إعادة استخدام ownership/root/metadata client، لا cache لسماح قديم؛ descriptor scan مبكر التوقف | لا TTFT/CPU/RAM أو حمل متزامن مقاس على VPS | تحسين مصدر مثبت محليًا؛ قياس الخادم وقبول النشر باقٍ |
| كتالوج Native والمزوّدات | كتالوج Native الأصلي، main50 + manual full search؛ visibility ليست منع استعمال يدوي؛ لا registry مكرر | النماذج الحرة وBig Pickle ظاهرة؛ فحص إدارة سابق:230مزوّدًا وصفحات صغيرة | لا يكفي ظهور «متصل» لإثبات اتصال نموذج خارجي؛ paid key/OAuth وsame-provider multiaccount لم يقبلا عمليًا |
| refresh7/14 يومًا | `native_catalog_maintenance.py` يعيد استخدام الصيانة و`models --refresh` الأصلي؛ admin manual action موجود | اختيار7/14 شوهد سابقًا؛ لم يُشغل refresh اليوم | CLI success ليس in-process reload؛ الجدولة الفعلية/الفشل/آخر cache على VPS لم تُعد مراجعتها؛ لا restart للمحرك |
| GitHub fresh link وإعادة الربط | حذف اتصال/حالات المستخدم فقط ثم OAuth state جديد وprompt=select_account؛ لا blacklist للحساب المفصول | منتقي GitHub الرسمي شوهد سابقًا بحساب testuser، وفيه حساب متصفح محفوظ؛ لا grant أو callback نهائي | إصلاح النافذة الجديدة أدناه مختبر مصدرًا فقط؛ رفض إعادة الربط حيًا لم يُعزل سببه بعد |
| عزل GitHub | user token، فحص App/installation ومستخدم Gateway؛ foreign installation409 | لم يُكمل ربط حسابين مستقلين حيًا | حراس منع النقل بين الحسابات تبقى؛ لا يعد ظهور حساب github.com المحفوظ دليل تسرب مستودعات |
| GitHub lazy/selective | picker metadata فقط؛ shallow/single branch/no-tags؛ sparse عند working_paths؛ واجهة تطلب full-copy consent | لا استنساخ جديد أو قياس network/disk اليوم | جزئي: لا partial clone؛ حماية ذروة استهلاك clone ليست مثبتة؛ واجهة consent لا تكفي وحدها لفرض اختيار صريح في جميع عملاءAPI |
| Smart Preview الموجود | static/diff وrunner/worker client/snapshot/leases موجودة؛ start صريح، لا محرك جديد | قبول Node/root/nested/NewTab بتاريخ18أكتوبر موثق بصور/قول المالك في أرشيف Work§56 | لا تعِد وصفه «غير منفذ بالكامل» اعتمادًا على سياسة16أكتوبر؛ حالة worker الحية اليوم وعزل حسابين و300ثانية وbuild frameworks الأخرى غير متحققة |
| إدارة البريد/المستخدمين | جداول وإعدادات وهوية فريدة/edit وأرشفة آمنة وسياسات إشعارات | قبول إداري سابق:20صف خدمة،17مدعومة و3غيرمتاحة؛ edit/theme وخيارbackup حُفظا واستُعيدا | Resend Receiving403 عائق مفتاح القراءة السابق، وليس عطل Native؛ لا طلب أو تغيير مفتاح هنا؛ لا حذف حسابات لاختبارها |
| الباقات والسعة | حدود العمل الحالية محلية50MiB وGitHub512MiB، ليست Silver/Gold التجارية | لا قياس سعة جديد ولا عملاء فعليون بحسب المالك | Silver800MB/Gold2GB لكل مشروع مؤجلة؛ يلزم مجموع الحساب/عدد المشاريع/clone+build accounting؛ مراجعة عند50عميلًا فعليًا، وأبكر عند التشبع |

### 15.2 توضيح المالك الملزم وإصلاح GitHub الصغير

**الفصل لا يمنع عودة حساب GitHub نفسه.** «غير متصل» وصف للحالة المحلية وليس رفضًا للحساب. يجوز للمستخدم نفسه إعادة ربط حساب GitHub نفسه بعد الفصل بتفويض جديد؛ لا تستعد الرموز أو حالات OAuth القديمة. لا تُحذف حماية installation المرتبط بحساب Gateway آخر لإخفاء409؛ هذا نقل ملكية مستقل يحتاج سياسة واضحة إذا أراده المالك لاحقًا.

الخلل المثبت: ثلاثة مداخل Frontend كانت تستعمل `window.location.assign(next.url)` فتنقل نفس التبويب. جُمعت في `window.startFreshGithubConnection` الموجودة بدل إنشاء خدمة؛ تحجز نافذة منفصلة فور ضغط المستخدم قبل أي await، تفصل opener، ثم تأكيد وPOST مصادق وOAuth أصلي. إذا حُظرت النافذة، لا POST ولا مسح للاتصال ولا fallback إلى التبويب القديم. الإلغاء/خطأAPI/تبديل حسابGateway/إغلاق النافذة يمنع التنقل المتأخر؛ النقر المكرر لا يكرر الطلب. يُقبل عنوان GitHub HTTPS ومسارauthorize المحدد فقط؛ لا tokens أو secrets إلى المتصفح. إدارة Connections تمسح عرض اتصالها القديم بعد بدء الربط. لا زر تفويض إضافي أو تغيير تصميم.

النوافذ العادية تشارك cookies موقعGitHub؛ لا يستطيع الموقع فرض private/incognito أو متصفح جديد خالٍ من الجلسات، أو إجبارGitHub على إعادة كلمة المرور عند وجود جلسة صحيحة. تدفق GitHub المدعوم هو `prompt=select_account` مع «Use a different account»؛ يستطيع المستخدم اختيار الحساب نفسه أو غيره. لا نزعم أن نافذة جديدة تعزل حسابGitHub أو أنها تمحو منح التطبيق الخارجية. إذا كان شرط المالك جلسة خاصة إجبارية فهذا **قيد متصفح غير قابل للفرض من الموقع**، لا سبب لرفض نفس الحساب. المراجع الرسمية: [GitHub account picker](https://github.blog/changelog/2024-06-07-account-picker-updates-for-oauth-and-github-app-sign-in/) و[MDN window.open](https://developer.mozilla.org/en-US/docs/Web/API/Window/open).

لم يُثبت سبب رفض callback على TEST؛ يجب التقاط outcome/status آمن عند محاولة جديدة دون جمع OAuthcode/state/token أو عرض موارد الآخرين. لم تُضغط Continue أو تمنح صلاحيات جديدة لهذا الغرض. لا اعتبار ظهورpicker أو اختبارvendor mock قبولًا خارجيًا نهائيًا.

ملفات التشغيل في هذه الدفعة فقط: `enhancements.js`, `dashboards.js`, `management.js`, `index.html` (cache tags). لا تغيير runtime Backend أو GitHub keys أو shared Native أو ports/config/DB. الاختبارات: `backend/tests/test_github_boundaries.py` أضيفت حالة disconnect→fresh OAuth→نفس installation901 والمالك نفسه مع بقاء اتصال المستخدم الآخر902؛ `tests/browser/test-github-fresh-link.cjs` و`test-github-customer-setup.cjs` تنفذ المساعد الحقيقي.

### 15.3 القياسات والاختبارات — المصدر منفصل عن TEST

- هذه الدفعة: **41 Backend PASS** (27GitHub boundaries و14cleanup)، **10 fresh-window DOM PASS**، **5 management/customer setup DOM PASS**، **29 Native UX VM PASS**. السيناريوهات محلية بمحتوى اصطناعي وSQLite/vendor mocks؛ ليست PostgreSQL TEST أو تفويضGitHub خارجيًا. تحذير AnyIO deprecation واحد قائم. فشلت أول محاولة جمع pytest بسبب تشغيل entrypoint دون module ثم صححت إلى `python -m pytest`؛ وفشلت fixture قديمة لا تحمل المساعد المشترك بعد توحيده، فحملت المساعد الحقيقي وأعيدت بنجاح؛ لا اختبارات منتج مستبعدة لإخفاء فشل.
- إصلاحات `ef5f114961adf04cb0a36b94822c688a64089592`:77Backend و29VM PASS **مسجلة في الجلسة السابقة**، لا يعاد نسبها كتجربة خادم اليوم. تضمنت حماية `.env*`,auth.json,credentials.json,.git/.ssh/.aws/.config/.opencode والمفاتيح في file/attachment/approval/export، وحظر السلوك التنفيذي غير المعروف.

| Benchmark اصطناعي سابق قابل للإعادة | قبل p50/p95 ms | بعد p50/p95 ms |
|---|---|---|
| HTTP/ORM Native authorization |9.760 /15.837|7.272 /12.227|
| فحص حصة3000ملف|31.088 /42.973|7.385 /12.878|
| رفض شجرة متجاوزة للسقف|31.248 /37.244|0.136 /0.327|

SELECT11→7؛ metadata fixture بقيت session1+toolIDs1، وفحص provider الحقيقي إضافي عند الحاجة ولم يُحذف. CPUmedian9.503→7.133ms؛ peakRSS101892→101812KiB فرق ضئيل لا يدعم ادعاء تحسنRAMالخادم. الأمر `python tests/performance/native_control_plane.py --baseline-ref eab7662` في بيئة المتطلبات؛ لا TTFT/network/clone/build VPS measurements. scan ليس hardquota يمنع Native من الكتابة أثناء التشغيل؛ concurrency/TOCTOU وOSحدود لازمة قبل إطلاق عام.

**بصمات TEST العامة أُعيد فحصها27أكتوبر: HTTP200 وكلها تطابق eab7662، وليست إثبات BackendSHA:**

| الأصل | SHA256 |
|---|---|
| enhancements.js | f4062883b1f3c9bbf3b52470e4866bd8b0b79d78abdc56d5e43eaabbab13b083 |
| dashboards.js | 28f57117576611dcd84c31ea70c7dae02888cf916d4d2446f4935071c1e758a1 |
| management.js | f1758439f86689fdff0c58ba4aa26aee7a2f0d9a267370256d9e46bc254b8bb8 |
| native-session-client.js | 58f350d732a4acd54a4dc427b359e1d94d8b3583aeb870ebdb114b4b52ce68b0 |

السجل حي وTodo2/16 والنماذج ظاهرة على TEST اليوم، لكن سؤال سابق معروض كفشل تاريخي وليس اختبارًا ناجحًا جديدًا. لا يُكشف محتوى حساس من تاريخ المحادثة. لا قياس جديد للأحداث أثناء تنفيذPrompt أو لرسالةuncertain. لا مُرفقات أو مشاريع أو محادثات حُذفت.

### 15.4 التعارضات المحسومة والعوائق

1. V3.8/3.9 وWorkمذكرات متعددة: المرجع هذا الملف؛ الأرشيف دليل مؤرخ فقط. `AGENTS.md` يحيل إليه أولًا وآخرًا. تعليمات workflows القديمة ليست تفويضًا لتعديلها الآن.
2. Preview «لاworker مطلقًا» في وثائق16أكتوبر مقابل قبول18أكتوبر: الأخير يلغي نفي التشغيل التاريخي المطلق، لكنه لا يثبت جميعframeworks أو العزل الحالي. أُبقي التنفيذ كما هو؛ لم تلمس هذه الدفعةPreview.
3. «لم يُنشر شيء» في مذكراتقديمة مقابل نشر14ملف وPIDunchanged: التاريخ مثبت بتصريحالمالك؛ لا يعاد install/restart. ef5f114 وإصلاح النافذة الجديد لهما نشر منفصل لم يحدث بواسطةWork.
4. حفظ الملفات عند «ربط جديد» مقابل محو نسخةGitHub عند «فصل صريح»: عمليتان مختلفتان كما في أرشيف27أكتوبر؛ الداخلية وبياناتNative محفوظة. لا حذف فعلي بمرور هذه المراجعة، ولا broadcleanup/reset.
5. اشتراك800MB/2GB مقابل512MiBفيالكود: المستقبل ليس إعدادًا قائمًا؛ لا تغييرحدودأوDBبلاقياس/قرار. قبل50عميلًا نفحص الموارد، لا نعتبر حساباتQAعملاءفعليين.
6. Nativeprocess-global provider slot وMCPauth وalwayspermission cache حدود حقيقية؛ ملكيةGateway لا تثبت عزلهذهالمخازن. لا نسخcredentials أو خدمةAIجديدة أو تشغيلMCP/Shellلتجاوزها. لا إطلاق خارجي قبل حلcriticalisolation.
7. partialclone الخاص: تحتاج promisor-fetchcredential-safe وحارس ذروةclone/checkout وقياس public/private قبل --filter؛ لا يُضاف flagفقط ثم يدعى selective network. لا تخزينtokenفيgitconfig/argv.

### 15.5 ترتيب المتابعة والنشر الآمن

1. المالك ينشر يدويًا فقط، دون تعديل Workflow أو config. افحص preimages للملفات الأربعة أعلاه واحتفظ بنسخة احتياطية خاصة، ثم حدّث الحزمة المتطابقة. توقف عند أي تغيير خادم مجهول بدل الكتابة فوقه. لا restart لـNative. هذه دفعة Frontend لا تحتاج restart لـBackend. مصدر ef5f114 يحتاج Backend وFrontend متوافقين في إصدار مستقل بعد المصالحة؛ لا تكتفِ بثلاثة ملفات UI.
2. بعد نشر المالك: testuser → ربط جديد → نافذة منفصلة → اختيار الحساب نفسه → callback → الحساب والمستودع المصرح به. اختبر الفصل والعودة بنفس الحساب مع بيانات اصطناعية مملوكة، دون حذف بيانات حقيقية. اختبر حساب GitHub آخر مستقلًا وأخطاء403/409 والحالات المنتهية، واحفظ statuses وsynthetic markers فقط. لا تزل منع foreign installation لمجرد تسهيل إعادة الربط.
3. قبول مصدر ef5f114 الحي: حسابان ومشروعان وجلسات وملفات اصطناعية؛ رفض الوصول الأجنبي؛ عدم تداخل SSE؛ عدم قبول permission/question reply أجنبي؛ Stop/Recover بعد lost ack دون إعادة إرسال؛ رفض أداة خارج root؛ عدم إعادة إسناد credentials. قس auth/TTFT/calls/CPU/RAM على TEST قبل وبعد. لا Shell قبل OS isolation.
4. selective clone: قس network وGit objects وcheckout peak disk والوقت للعام والخاص، مع فشل وtimeout وrollback مضبوط دون المساس بمشروع قائم. ثم اقبل filter فقط إذا نجحت الاختبارات. Preview الموجود: افحص حالة worker قراءةً أولًا عند اختبار المسار، ثم static/diff و300 ثانية والعزل وframeworks بمشروع اصطناعي؛ لا تشغيل لبنية جديدة.
5. مؤجل حتى موارد أكبر أو اشتراكات حقيقية: توسيع حجم Workspaces التجاري، dynamic builds الأثقل ومزيد من slots، وworker host إضافي بحسب benchmark. الأسعار وعدد المشاريع غير متفق عليهما. الأمن الأساسي وتقليل metadata لا يؤجلان إلى الإطلاق.

لا نشر تلقائي؛ لا rollback location جديد على VPS لأنه لم يُكتب عليه شيء. لم تتغير `.env` أو secrets أو databases أو Native cache/storage أو process/installation أو Nginx أو IPs/ports أو master/LIVE/workflows/Preview. GitHub source SHA الخاص بهذه الدفعة يضاف بعد نشر المصدر؛ لا يُختلق SHA أو PID أو backup.

### 15.6 تسليم المصدر

نُشر إصلاح النافذة وإثبات إعادة ربط الحساب نفسه على `updates` في commit `5379117812dd166663bd4c25e271c38facade80c`، بالشجرة المختبرة `f2a9463298f56066087156084865ebc14b11fada`. قورن كل Git blob والشجرة الكاملة بالنسخة المحلية، وحُدّث ref بشرط الرأس السابق دون force. هذا نشر مصدر إلى GitHub وليس نشر TEST. ملفات التوثيق/AGENTS/مؤشر handoff والأرشيف تحديث مستقل لهذا المرجع. لا يُدّعى CI أخضر أو deployment أو قبول OAuth نهائي من نجاح كتابة commit.

---

## 16. توجيه28أكتوبر2026 — GitHub Disconnect/Reconnect فقط

**هذا التوجيه الأحدث ينسخ سياسة حذف نسخ العمل عند فصل GitHub في السجل السابق.** الفصل لا يزيل ملفات المشاريع أو تعديلات غير مرفوعة أو Project/Workspace records أو تاريخ Native. النطاق الحالي GitHub identity/OAuth/callback/disconnect فقط؛ لا إصلاح للمحادثات أو Native أو Preview أو الباقات. تبقى بقية المذكرة محفوظة بأدلتها التاريخية، ولا تعاد مهامها ضمن هذه الدفعة.

### 16.1 مقارنة الرأس الفعلي وحسم التغييرات المتزامنة

بدأ الفحص من `1858459c439b9c8d396b76f246ec3d295f7214b0`. أثناء الرفع ظهر رأس متزامن `50adab67694eb58b340269c875eaa0662f7a5e97` مع7commits في `github.py` و`enhancements.js`. توقف الدفع قبل الكتابة؛ قُرئت الفروق وجرى rebase ودمج يدوي دلالي دون force أو فقد تلك الإصلاحات:

- لا يمسح Connect اتصالًا قائمًا: يلزم Disconnect صريح أولًا، وإلا409؛ إلغاء الربط لا يحدث لمجرد طلب اختيار مستودع آخر.
- لا يُفرض تثبيت جديد إذا أعاد GitHub تثبيتًا صالحًا. أما الفصل الصريح فيحاول إزالة التثبيت الشخصي المثبت أنه مملوك، حسب الضوابط أدناه.
- تُبطل محاولات OAuth الموازية بعد تأكيد الربط؛ الطلب المتأخر لا يستبدل الاتصال الجديد.
- حُفظ أحدث تنقل OAuth في **التبويب نفسه** كما في50adab6، دون إعادة إدخال popup فارغ أو تبديل سلوكه مرة أخرى. هذا يتقدم على وصف popup في§15 باعتباره حالة إصدار سابق. المطلوب في التوجيه الحالي اختيار حساب وتأكيده، لا الادعاء بأن التبويب/النافذة الجديدة يمحوان cookies.

### 16.2 أسباب وفجوات مؤكدة في المصدر

1. مسار الفصل القديم كان يستدعي `expire_github_copies` ثم `sweep`؛ فُصل ذلك تمامًا عن GitHub disconnect وفق قرار المالك الأحدث. صيانة retention المستقلة لم تُعدّل ولم تُشغّل هنا.
2. الـCallback القديم تحقق من state ومستخدمه المخزن، دون مطابقة جلسة Gateway الحالية؛ كان يستطيع إنشاء اتصال مباشرة بعد code exchange دون تأكيد هوية محلي. لم يقرأ `/user` لإثبات معرف GitHub الشخصي مستقلًا عن مالك installation، الذي قد يكون مؤسسة.
3. cookies Gateway من نوع SameSite=Strict لا تُرسل في أول navigation آتٍ من GitHub. إضافة require_user إلى GET callback وحده ليست حلًا؛ ستفشل المصادقة حتى مع جلسة صحيحة. أُضيفت صفحة عودة محلية قصيرة ثم POST من الأصل نفسه لمطابقة جلسة Gateway قبل معالجة الرمز، دون إضعاف cookie.
4. كان هناك تسجيلان لـ`/api/github/status`؛ نسخة workspaces المسجلة أولًا حجبت مسار GitHub المخصص. أُزيل **هذا endpoint المكرر فقط** من workspaces، وأضيف regression لوجود مسار واحد؛ لا تعديل لأدوات الملفات أو Native.
5. كان enhanced bootstrap يمحو علامة GitHub منURL قبل اكتمال استعادة صفحة العميل؛ أزيل هذا السباق. بعد العودة يفتح العميل Connections والإداري صفحة GitHub، ويُقرأ status الأصلي؛ query flag ليس دليل ربط.
6. حلقة فرض تثبيت تطبيق موجود عولجت أيضًا في98b91ce المتزامن؛ حُفظت النتيجة ولم تُنسب من جديد إلى هذه الدفعة. لا يوجد trace نهائي من callback على VPS يثبت أن كل فشل سابق سببه هذه الحلقة أو إعداد Setup URL بعينه؛ إعداد GitHub App الخارجي لم يُعدّل أو يُفترض أنه صحيح.

### 16.3 التنفيذ الحالي

- **Unique connection identity:** يُعاد استخدام UUID الموجود أصلًا في `GithubConnection.id` بوصفه `connection_id`، وتُولد UUIDv4 جديدة للمعاملة الجديدة ثم تُحفظ فقط عند تأكيد ناجح. لا registry أو service أخرى. `gateway_user_id` ثابت؛ `github_user_id` هو `/user.id` الحقيقي من GitHub ولا يُخترع أو يُغير.
- `oauth_state` عشوائي256bit، مؤقت15دقيقة، single use، مرتبط بصاحب Gateway و`AuthSession.id` وبـconnection UUID. Connect جديد يمحو معاملات هذا المستخدم السابقة تحت قفل صف المالك، ويصدر معاملة جديدة في transaction واحدة. Disconnect/Confirm يحصلان على قفل المالك نفسه؛ الفحص والتعديل متسلسلان على PostgreSQL. قبول التزامن الفعلي على PostgreSQL ما زال مطلوبًا؛ SQLite tests ليست إثبات row locks.
- GET callback لا يحفظ اتصالًا، ولا يستخدم state كبديل عن جلسة Gateway. يعرض form محليًا إلى POST `/api/github/callback/complete`، مع CSP وno-store وإزالة query منhistory وno-referrer. POST يتحقق من جلسة Gateway الحالية وstate/user/session/expiry/consumption، ثم code exchange و`GET /user` و`GET /user/installations` من GitHub. لا تضع codes أو tokens في query إعادة التوجيه إلى الواجهة.
- تعود النتيجة **pending**، بمفتاح مشفر مؤقت في `GithubAuthState.pending_payload`؛ لا وصول للمستودعات ولا اتصال نشط. تعرض الواجهة اسم GitHub الحقيقي وinstallation المصرح به، وCheckbox تأكيد صريح وزر Confirm. لا OAuth access/refresh token في JSON أو localStorage. Pending status لا يظهر إلا للجلسة المالكة نفسها.
- POST `/api/github/confirm` يعيد التحقق من الجلسة والهوية وعضوية installation وAppID وصلاحيات Gateway الحالية، ثم يحفظ الاتصال. قيود فريدة على GitHub userID وinstallation تمنع إسنادهما لحساب Gateway آخر. يوجد رفض409 سباق uniqueness مع rollback؛ حذف pending states وإضافة الاتصال في معاملة واحدة. ربط الحساب نفسه بعد فصل صريح مسموح، بمعرّف connection جديد.
- إذا لم يوجد installation، يستخدم زر تثبيت صريح التدفق الرسمي، ويحفظ expected GitHub identity في المعاملة نفسها. `installation_id` القادم من query ليس إثبات ملكية؛ يلزم OAuth والتحقق من actor نفسه بعد العودة. اختلاف الهوية يرفض الربط؛ لا تحايل على جلسة GitHub أو سحب عام لمستودعات App.
- `/install` و`/authorize` القديمان يعيدان المستخدم إلى بدء ربط صريح، ولا يحذفان اعتمادًا أو ينشئان اتصالًا من GET.
- الفصل يحذف connection ورمزه وجميع OAuth/pending records لذلك المستخدم. يُستدعى GitHub `DELETE /applications/{client_id}/token` ببيانات تطبيق المنصة على الخادم فقط، ثم check-token POST للتثبت من404. **لا يستخدم DELETE grant** لأنه يبطل جميع tokens لذلك GitHub user وقد يمس اتصالًا آخر. refresh token لم يكن مخزنًا أصلًا في Gateway؛ لا يُنشأ له تخزين جديد.
- طلب الفصل الصريح يحاول أيضًا إزالة **التثبيت الشخصي المملوك فقط**: `/user.id` يساوي `installation.account.id`، النوعUser، وAppID صحيح، ومعرف الاتصال الحقيقي مطابق إن وُجد. بعدها DELETE `/app/installations/{id}` وGET للتحقق من404. لا تُزال مؤسسة أو installation لمستخدم collaborator أو ملكية غير مثبتة بسلطة App JWT؛ تعود `owner-review-required` وتلزم مراجعة مالك GitHub. فصل إداري لاتصال عميل أو webhook لا يمنح تلقائيًا صلاحية uninstall خارجي. لم تُنفذ أي uninstall حقيقية في هذه الجلسة.
- عند فشل GitHub أو فك اعتماد قديم، تُزال السلطة المحلية ويُعاد `revocation=unconfirmed` أو حالة إزالة التثبيت الصادقة؛ لا يقال إن الإبطال الخارجي تحقق. المهل محدودة، ولا background queue أو daemon جديد. لا ضمان إلغاء طلب GitHub كان قد قُبل بالفعل قبل الفصل.
- الحالة في التبويبات تُبطل بإشعار متعلق بمعرف Gateway user فقط، دون tokens؛ العرض القديم لا يخول API. لا كاش repo server-side مستقل موجود يلزم حذف صفوفه؛ القوائم تُجلب من GitHub بتوكن صاحب الاتصال، وتبقى الاستجابات الخاصة no-store.
- Uvicorn access log يزيل code/state من query مسار callback. حالة access log في Nginx الفعلي **غير مفحوصة عبر SSH** ولا يُدّعى أنه صار منقحًا بمجرد هذا filter؛ لا تغيير config ضمن هذه الدفعة.

**معرف GitHub account لا يتبدل بإعادة الربط.** إذا أُزيل تثبيت شخصي فعليًا ثم أُعيد تثبيته، يصدر GitHub installation ID جديدًا وفق خدمته؛ لا نصنع ذلك ID بأنفسنا ولا نعد به قبل التحقق الخارجي. Cookies GitHub ومنح الحساب الخارجية ليست قاعدةGateway. حتى مع ظهور حساب محفوظ، لا يكتمل ربط Gateway الآن إلا باختيار الحساب وتأكيد هويته صراحة. هذا لا يثبت أن شخصًا على جهاز مشترك هو المالك الأصلي إن استعمل جلسة GitHub المفتوحة واختارها عمدًا؛ لا نختلق reauthentication غير مدعوم.

### 16.4 الملفات وحزمة النشر القابلة للمراجعة

ملفات التطبيق/الترحيل10 فقط:

- `app.js`, `dashboards.js`, `enhancements.js`, `management.js`, `index.html`.
- `backend/app/services/github.py`, `backend/app/routes/github.py`, `backend/app/routes/workspaces.py` (إزالة GitHub status المكرر فقط)، `backend/app/models/workspace.py`.
- `backend/alembic/versions/0028_github_connection_identity.py`.

`0028` additive: Github userID/login وunique nullable index، وربط OAuth بـAuthSession وconnectionUUID وencrypted pending payload. **لا حذف أو تبديل معرفات الاتصال القديمة أو حسابات أو مشاريع أو مفاتيح تشفير.** الاتصالات القديمة تحفظ كما هي؛ state قديم غير مرتبط بجلسة يرفضه التدفق الجديد. لا downgrade مدمر تلقائي.

الاختبارات الدائمة7ملفات: `backend/tests/test_github_reconnect_security.py`, `test_github_boundaries.py`, `test_github_copy_cleanup.py`, `test_admin_github_diagnostics.py`، و`tests/browser/test-github-confirmation.cjs`, `test-github-fresh-link.cjs`, `test-github-customer-setup.cjs`. تغيرت assertions التي كانت تطلب الحذف/الربط التلقائي صراحةً لأن قرار المالك نسخ السلوك القديم؛ لم تُسقط حراس الملكية لإخفاء فشل.

حزمة المراجعة `releases/github-reconnect-20261028.json` تحصر الملفات العشرة، وبصمات before من50adab6 وafter للشيفرة المختبرة، وشرط غياب ملف الترحيل الجديد قبل الإضافة. هذه **manifest وليست deployer أو إثبات ملفات الخادم**. تحقّق من preimages الحقيقية؛ توقف عند أي تعديل غير معروف بدل overwrite. لا `.env` أو secrets أو databases dumps داخل الحزمة.

إجراء النشر المطلوب: backup خاص حقيقي لملفات preimage وخطة استعادة موثقة، ونسخة TEST DB مع تحقق هويتها وصلاحيات مالكها قبل migration. يجب التثبت أن الرأس الحالي0027؛ إذا كانت26/27 أو ترحيلات أخرى ناقصة فتوقف، ولا تطبق تغييرات البريد أو الباقات ضمن مهمة GitHub فقط. طبّق الحزمة المتوافقة في نافذة صيانة Gateway TEST، ونفذ migration0028 عبر البوابة الموثقة، ثم أعد Gateway TEST فقط بعد فحص تبعيات الخدمة. لا Native restart، ولا Nginx/ports/IP/env/workflow edits. تراجع التطبيق يستعيد preimages فقط مع إبقاء الأعمدة الجديدة والبيانات؛ لا يشغل downgrade. أداة full release الحالية لا توفر بنفسها backup/preimage protection كافية لهذا الطلب، فلا يطبق deploy شامل مجهول اعتمادًا على اسم الأداة.

### 16.5 الاختبارات والدليل الفعلي

**محليًا:62 Backend PASS،16 DOM PASS (7fresh link +5customer management +4identity confirmation)**، وتحذير AnyIO deprecation قائم. سلسلة28migration ذات رأس0028 ناجحة، Python/JS syntax وdiff checks ناجحة. اختُبر PostgreSQL DDL الناتج من0028 وأنه additive، لا تشغيل ترحيل على TEST. Backend tests تستعمل HTTP/ORM وSQLite واستجابات GitHub اصطناعية؛ ليست credentials أو شبكة GitHub حقيقية.

| القبول | نتيجة الاختبار المحلي | نتيجة TEST الفعلية بهذه الدفعة |
|---|---|---|
| فصل connection/tokens/states دون الملفات أو سجل الجلسات | PASS؛ source github/blank/template وsymlink وunpushed marker | BLOCKED؛ لم يُطلب فصل اتصال حقيقي على النسخة القديمة |
| revoke token ثم check404 وuninstall شخصي ثم verify404 | PASS مع GitHub mock؛ org/collaborator ممنوع | BLOCKED؛ لا revocation/uninstall خارجية منفذة |
| UUID/state جديدان وعدم استعمال state قديم | PASS | BLOCKED حتى نشر0028 |
| AdminA/GitHubA، CustomerB/GitHubB، CustomerC بلا اتصال | PASS HTTP/ORM بثلاث هويات Gateway واثنتين GitHub اصطناعيتين | BLOCKED؛ لم تتوفر ثلاث حسابات مخولة وحساب GitHubB مستقل |
| remembered GitHubA عند GatewayB لا يربط تلقائيًا | PASS؛ pending فقط، و409 عند identity/installation مملوكين لغيره | صفحة اختيار GitHub ظهرت سابقًا؛ لم يُضغط Continue لمنح مواردA إلىB |
| current Gateway user/session، expired/used/parallel/cancel/tamper | PASS؛ same-user new-login مرفوض أيضًا | BLOCKED؛ cookie bridge والمتصفحات المشتركة/الجديدة تحتاج دورة حية |
| account/repository isolation وعدم حذف بيانات الغير | PASS؛ توكن كل هوية وقائمة repo منفصلة | BLOCKED لربط الحسابين الخارجي النهائي |
| callback متبوع بتأكيد يعرض GitHub username الصحيح | PASS HTTP/ORM وDOM | BLOCKED؛ لا PASS حي من نجاح source tests |

آخر فحص28أكتوبر: أصول TEST العامة200 تطابق50adab6؛ **لا تطابق دفعة التأكيد الجديدة**. enhancements SHA256 `8e5ff8632bf658a19d79c3ad5e5a5e9be08f3043d1e83a57ddb6c0a220cc6651`؛ app.js `ec6673d9637794760dc5c3a72b0e309bec54893d4c21ebeb0a76dd400aceba9b`؛ dashboards `97034c9906d298344ad14fe1a31880ed9174deb7ac6be7af6c776275eedc8468`؛ management `b6e4b059c18fc324b567223c4590663ac77a1a04f588928b6080a97868ab397e`. تطابق الأصول لا يثبت backend SHA أو migrations أوPID.

**العائق التشغيلي المحدد:** لا SSH key/host connection مهيأ في بيئةWork، ولا أداة متصلة لتشغيل workflow_dispatch. مجلد SSH المتاح بلا مفتاح أو إعداد اتصال؛ لم تتم محاولة تخمين كلمة مرور أو قراءة أسرار خادم. لذلك لم ينفذ Work backup أو migration أو restart أو deploy؛ لا rollback path علىVPS يمكن الإبلاغ عنه. يلزم وصول خادم مهيأ أو تنفيذ المالك للحزمة المراجعة، ثم قبول حقيقي بالحسابات المخولة. لا ترسل كلمات المرور أو tokens في الدردشة.

الأمر الأول للاختبارات:
`python -m pytest -q backend/tests/test_github_reconnect_security.py backend/tests/test_github_boundaries.py backend/tests/test_github_copy_cleanup.py backend/tests/test_admin_github_diagnostics.py backend/tests/test_admin_github_settings.py backend/tests/test_native_control_plane.py::test_github_connection_status_cannot_be_selected_with_other_user_id`

يتبعها ملفات DOM الثلاثة أعلاه في Node ببيئةjsdom و`python scripts/validate_migration_chain.py`. حالة قبول الأمان الخارجية **غير مكتملة**؛ لا تسجل PASS شاملًا ولا إطلاقًا عامًا. لا Native conversations/file tools/Preview/subscriptions أو shared services أوmaster/LIVE/workflows تغيرت. بعد النشر فقط: Aconnect→Adisconnect→Bfresh OAuth→Bidentity confirm→B repo isolation→Areconnect→Cdenied، مع cancel/expired/duplicate/wrong-user/parallel/shared/fresh browser، وتوثيق HTTP statuses بلا codes/tokens/cookies.

**تسليم المصدر:** commit `c658ee017656c48030145329ebbf12a85af4e663` على `updates`، parent `50adab67694eb58b340269c875eaa0662f7a5e97`، والشجرة المختبرة `924b786ab5ca77af75a2788f5fec3e6e7bc5dce1`. قورنت جميع blobs والشجرة، ودُفع CAS دون force. أُبقيت معرفات منشأ المشروع التاريخية وملفاته؛ ليست اعتمادًا ولا تمنح API وصولًا دون اتصال المالك الصحيح. مصدرGitHub ليس نشرTEST.


---

## 17. سجل PostgreSQL/Alembic TEST الموثق — 25–28 أكتوبر 2026 (إضافة 28 أكتوبر)

**النطاق:** قاعدة `opencode_gateway_test` وخدمة Gateway TEST فقط. هذا سجل تشغيل للأخطاء التي تكررت، وليس إذنًا بتغيير LIVE، أو إعادة تشغيل OpenCode Native، أو حذف بيانات مستخدم أو ملفات GitHub. احتفظ بأقسام هذه المذكرة السابقة دون استبدال.

### 17.1 ما ثبت سابقًا وما لا يجوز تخمينه

- حسب سجل فحوص TEST بتاريخ 22 أكتوبر: مالك قاعدة `opencode_gateway_test` هو `opencode_gateway`؛ أنشئ دور التطبيق المستقل `opencode_gateway_test_app`، ومنحت له صلاحيات استخدام/جداول/تسلسلات عامة. **GRANT العادي لا يمنح ملكية الجداول أو صلاحية تنفيذ ALTER TABLE.**
- في جلسات 25–26 أكتوبر تكرر `InsufficientPrivilege: must be owner of table email_verifications` في Migration `0025`، وعولجت ملكية جداول من ضمنها `email_verifications` و`users` لصالح دور TEST المخوّل، `opencode_gateway_test_app`. كما عولج أثناء التسلسل تعارض بيانات الهاتف ومحدودية طول `alembic_version.version_num` (جرى توسيعه إلى `VARCHAR(128)`). **هذه وقائع تاريخية وليست أوامر لإعادة تنفيذها الآن.**
- في يوم 28 أكتوبر، أكد سجل Alembic بداية الترحيل من `0027_email_notification_receipts` إلى `0028_github_connection_identity`. **لم يعد `0025` أو `0026` هو التعطل الحالي**؛ لا تعاود ترحيلات قديمة أو `alembic stamp` أو تعديل نسخ يدوي.

### 17.2 الخطأ الفعلي في GitHub Actions — 28 أكتوبر

- تشغيل Actions `40650390668`، SHA `7506fb5721d08723954fa03a99ae06b6ad12e31c`، نمط `deploy-test`: نجحت فحوص الشيفرة وSSH والوصول إلى TEST. سجل الناشر `FILES_TOTAL 109 CHANGES 10`، ثم فشل الاستدعاء:
  `sudo -n /usr/local/sbin/opencode-gateway-test-migrate upgrade` برمز 1.
- ظهر `GIT_ROLLBACK_APPLIED 50adab67694eb58b340269c875eaa0662f7a5e97`. التراجع عن ملفات التطبيق لا يثبت تراجع قاعدة البيانات، ولا يثبت نجاح نشر نسخة GitHub الجديدة؛ سجل الأدلة منفصلًا.
- سجل Actions لم يُظهر stderr الداخلي لـMigration Gate؛ **السبب الحقيقي استُخرج لاحقًا من Terminal**، وليس من التخمين حول SSH أو Workflow.

### 17.3 إصلاح Terminal المنفذ اليوم ومخرجاته

1. من المسار `/home/tahir/opencode-gateway-test/backend` نُفّذ:
   ```bash
   sudo /usr/local/sbin/opencode-gateway-test-migrate upgrade
   ```
   ظهرت `TEST_DATABASE_CONFIRMED` ثم `InsufficientPrivilege: must be owner of table github_connections` عند أول `ALTER TABLE` في `0028`.
2. محاولة لصق أوامر `ALTER TABLE ... OWNER TO ...;` مباشرة في Bash أعطت `ALTER: command not found` و`OWNER: command not found`، **ولا تعد تعديلًا للقاعدة**. SQL يجب أن يُنفّذ داخل `psql` أو هنا-دوك.
3. نُفّذ على TEST فقط، وظهرت `DO` ثم `ALTER TABLE` مرتين:
   ```bash
   sudo -u postgres psql -d opencode_gateway_test -v ON_ERROR_STOP=1 <<'SQL'
   DO $$
   BEGIN
       IF current_database() <> 'opencode_gateway_test' THEN
           RAISE EXCEPTION 'Wrong database';
       END IF;
   END
   $$;
   ALTER TABLE public.github_connections OWNER TO opencode_gateway_test_app;
   ALTER TABLE public.github_auth_states OWNER TO opencode_gateway_test_app;
   SQL
   ```
   **هذا تعديل ملكية الجدولين فقط، وليس قاعدة LIVE أو مستخدمي Gateway.**
4. إعادة تشغيل Gate تقدمت إلى `op.create_foreign_key('fk_github_state_auth_session',...)` ثم فشلت بـ `permission denied for table auth_sessions`. وأظهر الاستعلام `SELECT version_num FROM public.alembic_version` النتيجة `0027_email_notification_receipts`؛ الترحيل غير مكتمل والمعاملة تراجعت.
5. جرى توجيه منح صلاحية `REFERENCES` اللازمة للـForeign Key، دون نقل ملكية `auth_sessions`:
   ```bash
   sudo -u postgres psql -d opencode_gateway_test -v ON_ERROR_STOP=1 <<'SQL'
   DO $$
   BEGIN
       IF current_database() <> 'opencode_gateway_test' THEN
           RAISE EXCEPTION 'Wrong database';
       END IF;
   END
   $$;
   GRANT REFERENCES ON TABLE public.auth_sessions TO opencode_gateway_test_app;
   SQL
   ```
   ثم `sudo /usr/local/sbin/opencode-gateway-test-migrate upgrade`.
   **إفادة المالك في المحادثة: «تم النجاح»** بشأن هذه المرحلة. لا توجد هنا مخرجات `alembic_version` النهائية المصورة؛ عند الحاجة يكفي التحقق قراءةً فقط:
   ```bash
   sudo -u postgres psql -d opencode_gateway_test -c "SELECT version_num FROM public.alembic_version;"
   ```
   والمتوقع بعد النجاح: `0028_github_connection_identity`.
6. عقب ذلك أفاد المالك: «تم أيضا الرفع» لـ`deploy-test`. **هذا تأكيد مالك على النشر، وليس رقم تشغيل ناجح موثق في هذا السجل**؛ تحقق من run SHA الجديد وأصول TEST الفعلية عند اختبار GitHub OAuth. لا تخلط نجاح قاعدة البيانات بنجاح ربط حساب GitHub الحقيقي.

### 17.4 تفسير السبب والسياسة للترحيلات المقبلة

- المشكلة المتكررة: دور التطبيق المخصص لـTEST يستطيع الوصول إلى الجداول، لكنه قد لا يملك الجداول التاريخية التي يحتاج `ALTER TABLE` إليها. ولإنشاء Foreign Key إلى `auth_sessions` احتاج `REFERENCES` تحديدًا؛ لا داعي إلى نقل ملكية ذلك الجدول.
- لا تنقل **جميع** جداول public بلا مراجعة، ولا تمنح `SUPERUSER` لدور التطبيق، ولا تغيّر قاعدة LIVE أو كلمة مرور الدور المشترك. احفظ ملكيات وامتيازات بقية الجداول.
- بعد إكمال إصلاح GitHub OAuth الحالي، ينبغي مراجعة `/usr/local/sbin/opencode-gateway-test-migrate` وصلاحيات دور التنفيذ وسياسة إنشاء الجداول المستقبلية حتى يطبق `deploy-test` الترحيلات الجديدة آليًا وبأقل امتيازات، دون إعادة تصحيحات يدوية عند كل إصدار. **هذا عمل لاحق منفصل، لا يعوق قبول إصلاح GitHub الحالي.**
- لا تُشغّل الترحيل يدويًا مرتين إذا كان `alembic_version` بالفعل عند الرأس؛ استخدم نفس Gate المعتمدة بدل أوامر Alembic مع متغيرات قاعدة مجهولة. عند خطأ جديد، استخرج النص الحقيقي من Terminal ولا تغيّر الأدوار بالتخمين.

**حالة إغلاق السجل:** إصلاح ملكية `github_connections` و`github_auth_states` مؤكد بالمخرجات؛ `REFERENCES` ونجاح `0028` ونشر آخر تحديث **مؤكدة بإفادة المالك فقط** لحين استرجاع سجلات التحقق. لا دليل جديد هنا على نجاح OAuth/Disconnect/Reconnect متعدد الحسابات.

## 18. GitHub Callback — إصلاح Origin وتحقق النشر، 28 أكتوبر 2026

**النطاق GitHub فقط؛ لا Workflow/Native/Preview/LIVE/master أو تغييرات إعدادات/منافذ/قواعد بيانات.** فُحص الرأس `38b0f506853b9d0e0cd05225fc6f819b56b621d1` قبل التعديل، وتبين أن إضافته توثيق تشغيل PostgreSQL فقط. سجل المالك في القسم17 محفوظ كما هو.

### 18.1 دليل TEST والنشر الفعلي

- أُعيد جلب Actions run `40650390668`: المحاولة الثانية نجحت، job `122696656810`، بتاريخ28أكتوبر 07:51–07:52 UTC. سجلها `TEST_MIGRATION_GATE_PASSED` ثم `FULL_TEST_RELEASE_SUCCESS 7506fb5721d08723954fa03a99ae06b6ad12e31c`. فشل المحاولة الأولى وسجل rollback في القسم17 تاريخيان؛ لا يُعاد وصف المحاولة الأخيرة بالفشل.
- فُتح TEST فعليًا، ونجح تسجيل الدخول الآمن بحساب `testuser · customer`. Connections أعادت GitHub غير متصل مع زر «ربط GitHub جديد» فقط. الزر وصل إلى منتقي الحساب الرسمي وفيه `Continue as diirzoro` و`Use a different account`. اختيار الثاني أظهر نموذج تسجيل دخول GitHub آخر؛ لم يُربط حساب الأدمن بـtestuser ولم تُمنح صلاحيات جديدة.
- ظهور اسم GitHub محفوظ يأتي من جلسة github.com؛ لا يثبت توريث اتصال Gateway. لم تُستكمل دورة OAuth/callback/confirmation متعددة الحسابات؛ لا قبول شامل لربط المستودعات أو الإبطال الخارجي من نجاح النشر أو ظهورpicker.

### 18.2 العطل الذي أرسله المالك وإصلاحه

لقطة المالك بعد التفويض تعرض `{"detail":"Cross-site request denied"}`. فحص المصدر وجد صفحةGETcallback تحمل `<meta name="referrer" content="no-referrer">` ثم ترسل formPOST إلى `/api/github/callback/complete`. سياسةno-referrer تجعل Origin=null في navigation-mode POST طبقًا لمعيارFetch ووثائقMDN، فيرفضه browser_boundary بصورة صحيحة. هذه آلية متوافقة مع الخطأ المبلغ، وليست قياسًا لترويسات طلب المالك الخاص؛ لم تُجمع codes/cookies/tokens أو سجلات سرية.

الإصلاح الصغير في `backend/app/routes/github.py`: meta/header للصفحة يستخدمان strict-origin بدلno-referrer؛ يبقىhistory.replaceState قبلPOST. بذلك لا يُدرج OAuthquery فيReferer حتى عند غيابJavaScript، وتبقىOrigin الفعلية للطلب المحلي. Middleware العام يضعheader same-origin؛ meta strict-origin الأضيق تطبق على نموذج الصفحة. لم يُعدَّل middleware ولا استثناءCSRF أوSameSite، ولم تُقبلOrigin:null أو مصادر أجنبية. يبقى state مفرد الاستخدام مربوطًا بـGatewayUser+AuthSession، وOAuthpending لا يمنح مستودعات قبل تأكيد الهوية.

المرجع التقني: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy#effect_on_the_origin_header .

### 18.3 اختبارات وحدود الإثبات

**66 Backend PASS و16 DOM PASS.** أُضيفت4حالات انحدار في `backend/tests/test_github_reconnect_security.py`: صفحةcallback لا تستخدمno-referrer وتزيلquery قبلsubmit؛ POST محلي صحيح يصل303 إلىgithub=confirm دون اتصال نشط؛ Origin:null ومصدرأجنبيcross-site ومصدرأجنبيsame-origin جميعها403 قبل استدعاءGitHub ودون استهلاكstate. تستخدم الحالات الجديدة middleware الإنتاج الفعلي فيFastAPI+HTTPS fixture معORM/SQLite وvendor mocks؛ ليست متصفحًا خارجيًا أوPostgreSQLTEST. أول تشغيل كشف أنfixture الملكية القديم لا يركبmiddleware؛ أُضيفfixture جديد خاص بالحدود الفعلية وأُعيدت الحالات بنجاح، دون تخفيفأيassertion. تحذيرAnyIOdeprecation قائم. فحصgit diff --check ناجح؛ البداية افتقدتpytest فيPythonالعام فاستخدمتبيئةQAمؤقتة.

الملفان في commit الإصلاح `e5d28b80a48756ceb805e47b212e47fadb997812` على `updates` فقط. لا migration جديدة ولا تغييرات Frontend أو Workflow. لم يُنشر هذا الإصلاح على TEST بواسطة Work؛ النشر المثبت أعلاه `7506` يسبقه. التالي: نشر ملف `routes/github.py` المعتمد عبر إجراء TEST اليدوي مع preimage، ثم اختبار callback من GitHub الفعلي وهوية pending والتأكيد، ثم Disconnect/reconnect بحسابين مخولين. لا تُعلن زوال 403 حيًا قبل ذلك.

**حدود المعرفات:** GitHub userID ثابت من GitHub ولا يتغير عند Disconnect. ما يتجدد هو connectionUUID وOAuth state داخل Gateway. installationID لا نختلقه؛ قد تصدر GitHub غيره بعد uninstall/reinstall الحقيقي المثبت. لا معرفات عشوائية في URL تمسح cookies موقع github.com، ولا نافذة عادية جديدة تعزل الجلسة. لا يمس Disconnect ملفات المشاريع أو التعديلات غير المرفوعة؛ سياسة 73 ساعة المستقلة لم تُعدل أو تُختبر في هذه الدفعة.

## 19. قرار المالك وتنفيذ الفصل الكامل والحفظ قبل الحذف — 28 أكتوبر 2026

**الأولوية لهذا القسم في سياسة GitHub الجديدة.** أمر المالك «واصل» يجيز تنفيذ الفصل الكامل بإلغاء Grant، مع عرض حفظ التعديلات إلى GitHub والتحقق منها قبل حذف النسخة المحلية المختارة، أو الاحتفاظ بالنسخ 73 ساعة. الفصل العادي وحده لا يحذف الملفات. لا حذف للمشاريع الداخلية أو حسابات Gateway أو بيانات مستخدم آخر أو مخزن Native ومحادثاته. لا نشر تلقائي أو تعديل Workflow أو LIVE أو master أو Preview أو OpenCode أو إعدادات الخادم/المنافذ/المفاتيح/قواعد البيانات.

### 19.1 إلغاء التفويض الصحيح وحدود الملكية

- المصدر الآن يستدعي `DELETE /applications/{client_id}/grant` عند الفصل الصريح لاتصال نشط **متحقق الهوية** فقط، ثم `POST /applications/{client_id}/token` للتأكد من إبطال التوكن. Basic Auth للتطبيق يبقى على الخادم، ولا أسرار في الردود أو روابط Git. يلزم DELETE204 والتحقق404؛ DELETE404 لتوكن غير صالح لا يثبت غياب Grant كامل ويعود unconfirmed.
- يُطلب `/user` بتوكن الاتصال، ويُطابق id الحقيقي مع `GithubConnection.github_user_id` ويُرفض الإلغاء الشامل عند تعارض ملكية مع حساب Gateway آخر. سجل قديم بلا هوية مثبتة أو فشل GitHub لا يُدّعى إلغاء Grant له؛ يعود owner-review-required/unconfirmed، ويظل تنظيف الاتصال محليًا وإبطال توكنه ممكنًا.
- Grant يلغي **جميع توكنات حساب GitHub المحدد لهذا التطبيق**، وليس توكنات جميع عملاء التطبيق. صُحح التعليق القديم المضلل في المصدر. إلغاء pending/callback غير مكتمل وwebhook والتنظيف الإداري يحتفظ بإبطال التوكن المحدد فقط؛ لا يُسمح لمستخدم شاهد هوية GitHub أجنبية معلقة أن يلغي تفويض صاحبها الكامل.
- **لا Uninstall تلقائي من زر Disconnect الجديد.** إلغاء Grant وإزالة تثبيت GitHub App عمليتان مختلفتان. دالة إزالة التثبيت المحمية القديمة محفوظة، لكن المسار الجديد لا يستعمل سلطة App JWT لإزالة تثبيت قد تشترك فيه مشاريع أو مؤسسة. هذا ينسخ سلوك الإزالة التلقائية الشخصي في القسم16، ولا يمس تثبيتًا فعليًا من Work.
- كل إجراءات الواجهة تحمل connection_id الذي روجع. إلغاء تأكيد قديم لا يستطيع فصل اتصال أحدث؛ الإلغاء المعلق يتحقق كذلك من AuthSession الحالية. AuthSession الخاصة بتسجيل الدخول إلى Gateway لا تُحذف. Cookies موقع GitHub وGitHub User ID لا يتغيران بهذه العملية.

### 19.2 مسار المستخدم: مراجعة → حفظ وتحقق → حذف النسخة → فصل

- مساعد واجهة واحد `disconnectGithubWithReview` يُستخدم في Connections العميل والإدارة والمدخل القديم، بدلاً من اختلاف سياسات الأزرار. نافذة محدودة الحجم قابلة للتمرير تعرض جدولًا فعليًا: اختيار النسخ، اسم المشروع، المستودع والفرع، وعدد الملفات/Commits المحلية وقائمة ملفات قابلة للطي. لا محتوى ملفات أو tokens في المعاينة، ولا إدراج HTML من أسماء المشاريع.
- يختار المستخدم «حفظ إلى GitHub وحذف النسخ المختارة ثم الفصل» أو «فصل والاحتفاظ بالملفات 73 ساعة»، مع إلغاء متاح وتأكيد صريح للرفع والحذف النهائي. لا Push أو حذف بمجرد فتح النافذة أو Connect. النسخ المحجوبة لا تُختار للحذف؛ تبقى للمراجعة والتصدير. المشاريع الداخلية لا تدخل القائمة.
- GET `/api/github/disconnect/workspaces` يعرض فقط Workspaces المستوردة المملوكة لهذا الحساب والمرتبطة بتثبيت الاتصال الحالي، مع بصمة مراجعة تتضمن HEAD وحالة Git وبايتات الملفات المتغيرة. يتوقف عند أكثر من100 نسخة بدلاً من حذف غير معروض. لا يسرد نسخ حساب GitHub تاريخي مختلف ولا يقبل مسارًا من المتصفح.
- POST `/api/github/disconnect/workspaces/{workspace_id}` يأخذ connection_id وsnapshot وaction=save/delete فقط. save يعيد استعمال Commit وPush الموجودين، بأقفال المشروع والتحقق من الصلاحيات ورفض العمل النشط. لا force push، ولا Git credential helper عام، ولا توكن في URL/argv؛ النقل الموجود يمرر الاعتماد في بيئة عملية Git فقط. يُتحقق من SHA على الفرع البعيد قبل إرجاع saved/verified.
- delete يعيد التحقق من المستخدم والمشروع ونوعه وتثبيت الاتصال ومعرفه، وهدوء Native، وتطابق snapshot، ونظافة الملفات وعدم وجود ignored files، ثم **يقرأ SHA البعيد مجددًا من GitHub**. يعيد فحص الملفات وهدوء Native بعد انتظار GitHub. فشل أو تغيير أي منها يمنع الحذف. حالة وصول دائمة cache_expiring تسبق حذف المجلد المحسوب المملوك؛ لا مسار مطلق من العميل ولا حذف Project/WorkspaceSession من PostgreSQL. بعد نجاح حذف آخر نسخة متاحة للمشروع يُؤرشف سجل المشروع ليختفي من قائمة المشاريع النشطة، مع حفظ التاريخ.
- خطوات النسخ متتابعة ومكشوفة: إذا نجحت نسخة وفشلت تالية، تُذكر النسخ المنجزة ولا يُدّعى نجاح كامل؛ يبقى الاتصال حتى اختيار الفصل أو اكتمال الخطوات. النسخة المحذوفة سبق التحقق من رفعها؛ فشل Push أو التحقق يترك النسخة المحلية والاتصال. لا مزامنة صامتة أو حذف لتعديلات غير مرفوعة.
- فشل الحذف بعد وضع الحاجز يُبقي بيانات المشروع ومراجعه والنسخة البعيدة؛ يعاد خطأ صريح، وتبقى صيانة الملفات القائمة هي آلية استكمال التنظيف، دون daemon جديد. يلزم قبول PostgreSQL متزامن فعلي قبل ادعاء منع جميع سباقات runtime مشتركة؛ الاختبارات المحلية ليست OS confinement.

### 19.3 مهلة 73 ساعة وحماية البيانات

`GITHUB_RETENTION=73h` القائمة لم تُستبدل بخدمة جديدة. عند الفصل تُمنح النسخ المتبقية المرتبطة بالاتصال بداية مهلة جديدة عبر last_activity_at؛ لا تغيير مهلة المشاريع الداخلية. أُضيف حارس لصيانة النسخ العادية: clean Git + HEAD يطابق مرجع الفرع البعيد المحفوظ من Fetch + لا ملفات ignored. Git غير مقروء أو مسودة/ملف غير متتبع أو Commit محلي أو ملفات ignored أو stash أو فرع محلي مختلف يعني **الحفظ وعدم المسح بانتهاء المهلة وحده**. قد تبقى النسخة أطول من73ساعة حتى يراجعها صاحبها؛ لا وعد بمسح جميع النسخ آليًا بالموعد مع ضمان حفظ التعديلات في الوقت نفسه. الحارس لا يجلب API أو يعيد التوكن المفصول في كل دورة؛ لا تكلفة Git جديدة على تسجيل الدخول أو إرسال المحادثات. الحذف الصريح بعد إثبات GitHub المباشر له مساره المنفصل أعلاه.

### 19.4 الاختبارات والمصدر والنشر

**83 Backend PASS و21 DOM PASS** (7fresh-link +5customer-setup +4identity-confirmation +5disconnect-review)، مع تحذير AnyIO deprecation قائم. Python AST وJS syntax وgit diff --check ناجحة. اختبارات Backend تستخدم SQLite ومجلدات Git فعلية مؤقتة بمحتوى اصطناعي؛ GitHub API/remote Push وNative status محاكاة مقصودة، وليست حسابين خارجيين أو قاعدة TEST. اختبارات الواجهة تشغل المساعد الحقيقي في jsdom، وليست screenshots من TEST.

شملت الحالات الجديدة: التسلسل save→verify→delete→Grant، بقاء محادثات/AuthSession وملفات مستخدم آخر، رفض المسودة أو snapshot متغير أو تغير الملف أثناء انتظار GitHub، فشل Push، Native busy، مشروع داخلي أو اتصال مختلف أو مورد أجنبي، ignored files، Grant endpoint والمصادقة الخاصة بالتطبيق، عدم اعتبار404 إثبات إلغاء Grant، هوية غير متحققة/pending، إلغاء قديم لاتصال جديد، وحارس TTL. اختبارات DOM تثبت عدم الحذف قبل save/verified، وعدم الكتابة بعد رفض التأكيد، والتوقف عند تبديل الحساب، ورسالة فشل واضحة وإغلاق نافذة النجاح. لم تُحذف اختبارات أمان؛ تغير توقع Uninstall التلقائي إلى سياسة Grant الجديدة صراحةً.

أخطاء التطوير المصححة: fixture جديد احتاج DATABASE_URL اصطناعيًا قبل import؛ fixture الإبطال القديم احتاج دعم keyword grant؛ اختبار الزر القديم كان يتوقع فصلًا فوريًا فأصبح يختبر نافذة المراجعة الحقيقية. جميعها أُعيدت بنجاح؛ لم تُسقط assertions لتجاوز فشل منتج.

**Commit التنفيذ:** `845921683af7254870791640b73ea129032d38da`، parent `1c7a4f643cda5b3dd65397a1973c2e2ea002a1db`، tree `d7d1d5746437c2a38880a9b82df039ac20d7b0a1`، على updates فقط. تطابقت شجرة GitHub كاملة مع git write-tree المحلي قبل تحديث ref بشرط الرأس ودون force.

ملفات التشغيل السبعة: `backend/app/routes/github.py`, `backend/app/services/github.py`, `backend/app/services/workspace_cache.py`, `enhancements.js`, `dashboards.js`, `management.js`, `index.html` (نسخ assets). الاختبارات الأربعة: `backend/tests/test_github_disconnect_review.py` جديد، `backend/tests/test_github_reconnect_security.py`، `tests/browser/test-github-disconnect-review.cjs` جديد، `tests/browser/test-github-fresh-link.cjs`. المذكرة نفسها وAGENTS تحديث توثيق تابع. لا ترحيل DB جديد.

**لم ينشر Work هذه الدفعة إلى TEST، ولم ينفذ Grant revocation أو Push أو حذف بيانات حقيقية.** المطلوب نشر يدوي منسق لملفات التشغيل السبعة بعد مراجعة preimages ونسخها، ثم قبول بحسابين مخولين ومستودع اصطناعي: تعديل محلي→مراجعة الفرع→حفظ/Push→SHA بعيد→حذف النسخة المختارة فقط→فصل/Grant204→إعادة ربط وتأكيد هوية جديد؛ واختبار فشل الرفع، حفظ73ساعة، وحساب آخر. لا يكفي نجاح CI لإثبات ذلك. لا restart للمحرك أو تعديل Workflow/config/ports/DB/LIVE/master/Preview.

متابعة حماية البيانات في نفس الدفعة: commit `41930e018d4c96a513697df1e809ca6feb240e6c`، parent `845921683af7254870791640b73ea129032d38da`، tree `b303ac56be3ef30d16c5c6565199f84358b8687a`. أضيف منع حذف stash أو مراجع فروع محلية مختلفة، حتى مع clean HEAD، ومنع الحفظ التلقائي لمجلد repository متداخل أو submodule متغير. اختُبرت حالة stash الفعلية وفرع محلي إضافي في Git مؤقت، فأصبح الإجمالي النهائي83 Backend و21 DOM. هذه متابعة مصدر فقط، ولا تثبت نشر TEST أو إلغاء Grant خارجيًا.

## 20. المراجعة النهائية لعزل GitHub والتحقق المستقل — 28 أكتوبر 2026

> **قرار أحدث مُلزِم (28 أكتوبر، القسم 21):** السياسة القديمة في هذا القسم التي تفرض OTP على كل ربط جديد أُلغيت. يُحتفظ بمحتوى القسم 20 كأدلة تاريخية للاختبارات فقط؛ لا يُستخدم كتعليمات تنفيذ أو شروط قبول جديدة. المرجع التنفيذي لربط GitHub هو القسم 21 أدناه.



### 20.1 الفجوة المثبتة والقرار الذي اختاره المالك

راجع Work الرأس `854c4805aae0844363b3923adb6b8b4cb625797e` والتغييرات c658ee0/e5d28b8/8459216/41930e0 وأقسام16–19. لم تُعد كتابة Grant أو النقل أو الحذف أو Native. الفجوة: بعد حذف اتصال A عند Disconnect لا تبقى ملكية نشطة تمنع B من إصدار تفويض GitHub جديد للهوية نفسها من جلسة المتصفح المحفوظة؛ UUID جديد أوGrant ملغى لا يثبتان استقلال الشخص. قبل الفصل، unique GitHub userID/installation وحراس confirm يحفظون ملكية A النشطة بالفعل.

**القرار المعتمد صراحةً باختيار المالك في نموذج التفضيل:** «رمز بريد GitHub» بدل حجز ملكية دائم/مؤقت مع قاعدة نقل إضافية. كل ربط جديد، بما فيه العودة للحساب نفسه أو الانتقال المشروع إلى حساب Gateway آخر بعد الفصل، يتطلب رمزًا مستقلًا إلى البريد الأساسي **المتحقق لدى GitHub نفسه**. لا يُرسل إلى بريد Gateway الجديد ولا إلى حقل بريد يرسله المتصفح. لا جدول ملكية دائم ولا tombstone أو connection_id قديم للاحتفاظ به بعد الفصل، ولا آلية لتغيير GitHub userID.

الحالةA: اتصال A نشط → B مرفوض حتى لو أكمل GitHub OAuth وملك بريد GitHub؛ يلزم فصل A أولًا. الحالةB: فصل صريح → Grant وحذف السلطة المحلية طبقًا للقسم19. الحالةC: لا اتصال نشط آخر → OAuth جديد + إثبات التحكم ببريد GitHub المتحقق + تأكيد الهوية/التثبيت يسمحان بنقل مقصود، بينما «Continue» وحده أو معرفة UUID أو checkbox لا تكفي. هذا هو بديل سياسة الربط الدائم الذي اعتمده المالك، وليس ادعاء إنشاء حجز مستمر بعدDisconnect.

**الحد الصريح:** البريد قناة مستقلة عن جلسة GitHub فقط بقدر استقلال الوصول إليه. إذا كان الشخص الآخر يملك أيضًا جلسة بريد مفتوحة/وصولًا فعليًا إلى صندوق المالك، فلا تثبت هذه الخطوة شخصًا طبيعيًا ولا ملكية الجهاز. ليست ضمان MFA ماديًا أو إجبارًا على كلمة مرور GitHub. إن فُقد البريد، يُستعاد لدى مزوده أو يُحدَّث البريد الأساسي ويُتحقق منه داخل GitHub؛ لا fallback إلى بريد GatewayB ولا زر إداري شكلي يتجاوز الرمز. إذا بقي ارتباط GatewayA نشطًا وتعذر دخوله، تُستعمل استعادة حساب Gateway الحالية أو دعم محقق بشريًا قبل الفصل، ولا يُنقل اتصال نشط آليًا لمجرد OAuth/OTP جديد.

### 20.2 التنفيذ الأصغر دون بنية أو جدول جديد

- `GET /user` يثبت id الفعلي، ثم `GET /user/emails` بتوكن المستخدم يتحقق من primary=true وverified=true وصيغة بريد صالح. لا استخدام لبريد public في `/user` ولا بريد يورده العميل، ولا عنوان GitHub noreply. يلزم GitHub App user permission **Email addresses: read**؛ عدم السماح403 أو غياب بريد متحقق يوقف الربط برسالة حقيقية، دون تغيير إعدادات التطبيق أو رفع صلاحياته آليًا. المرجع: https://docs.github.com/en/rest/users/emails#list-email-addresses-for-the-authenticated-user .
- POST `/api/github/pending/email/send` و`/pending/email/verify` يحتاجان مستخدم Gateway وجلسة AuthSession ومعاملة connection_id التي يملكها. يُرفض إرسال أو تحقق هوية ما زالت مملوكة لحساب آخر قبل البريد. لا اتصال نشط أو مستودعات من مجرد callback أو إرسال الرمز.
- إرسال البريد يعيد استعمال `email_verification.smtp_settings` و`email_delivery.send` الموجودين، بدعم إعدادات SMTP/Resend/Brevo القائمة. لا مزود بريد أو خدمة أو Queue جديد، ولا تغيير إعداداتها. موضوع الرسالة يميز ربط GitHub عن تفعيل حساب Gateway؛ لا تُنشأ EmailVerification خاصة بالتسجيل ولا يُفعّل حساب Gateway من هذا الرمز.
- الرمز6أرقام، صالح حتى10دقائق وبحد انتهاء معاملةOAuth الأصلية15دقيقة، وخمس محاولات خطأ. digest باستخدام آلية HMAC الحالية مع domain خاص بـGitHub وnonce ومعرف الاتصال، داخل pending_payload المشفر القائم. لا رمز صريح في DB أو URL/JSON/logs، ولا عنوان البريد الكامل في الرد أو payload؛ يُخزن hash للبريد وعنوان مقنع فقط. بعد نجاح الرمز يزال digest ويظل إثبات مؤقت محمي على الخادم.
- resend يبطل الإثبات السابق ولا يصفر عداد التخمين. cooldown60ثانية وحد5طلبات في الساعة بحسب حساب Gateway وهوية GitHub معًا، عبر AccountAudit الحالي. المفتاح HMAC مختصر لهوية GitHub لا اسمها، فلا يتجاوز بإنشاء OAuth أو installation جديد أو تغيير username. PostgreSQL advisory transaction lock يسلسل نفس المفتاح بين حسابات Gateway دون Schema أو إعدادات جديدة؛ **تزامنه الفعلي على TEST لم يُقَس في اختباراتSQLite**.
- `/confirm` يفرض إثبات البريد على Backend حتى للـAPI المباشر، مع بقاء جميع حراس المستخدم والجلسة وstate والهوية والتثبيت وuniqueness. يعيد قراءة بريد GitHub الأساسي ويقارنه ببصمة الإثبات قبل إنشاء الاتصال؛ تغييره بعد الرمز يتطلب رمزًا جديدًا. لا إعادة استعمال لرمز اتصال A في اتصال B ولا حالة منتهية/مستهلكة.
- الواجهة الحالية تضيف نموذج رمز صغيرًا داخل بطاقة تأكيد الهوية، مع إرسال/تحقق ورسائل فعلية؛ زر تأكيد الربط يبقى معطلًا دون إثبات. لا تفقد اختيار التثبيت أو checkbox عند التحقق. الإرسال مجددًا متاح عند انتهاء الإثبات، ولا Refresh/streaming يعفي من تحقق Backend. لا popup أو iframe أو تغيير سياسة المتصفح.

### 20.3 مدة الاحتفاظ والموارد

المعلومات المؤقتة تبقى في GithubAuthState المشفر الموجود، لا سجلات ملكية دائمة. بعد confirm أو Disconnect تُحذف حالاتها طبقًا للتدفق الحالي؛ بعد انتهاء15دقيقة تفقد الصلاحية فورًا. أضيف `expire_pending_authorizations` كعملية DB قصيرة إلى **حلقة الصيانة القائمة** في Gateway كل300ثانية: تحذف حالاتOAuth المنتهية وعدادات إرسال البريد الخاصة بهذه الميزة الأقدم من24ساعة، بدفعات100 مرتبة. لا تمس اتصالات نشطة أو AuthSession أو AccountAudit غير متعلق أو مشاريع أو Native storage. إيقاف الصيانة/تراكم دفعات قد يؤخر الحذف المادي، لكنه لا يمدد قبول الحالة؛ تشغيل الصيانة الفعلي يحتاج قبول TEST. لا استدعاءات GitHub/SMTP من عملية التنظيف ولا daemon إضافي.

بريد الملكية يضيف API/SMTP فقط أثناء الربط الصريح؛ لا تكلفة جديدة على المحادثات أو SSE أو الملفات أو تحميل نماذج Native. تعديل `backend/app/main.py` محصور بإضافة مهمة GitHub إلى قائمة مهام الصيانة الموجودة، دون تغيير تشغيل Native/Preview/الخدمات.

### 20.4 الأدلة الحالية: المصدر منفصل عن TEST

- مصدر التنفيذ: `86612dfed2c631a4aff61d0d847e855bef22947a`، parent `854c4805aae0844363b3923adb6b8b4cb625797e`، tree `d6ed3293e4057531d1491f9ea439d3fc3664a7a5`. تطابقت الشجرة المحلية قبل دفعupdates بشرط الرأس ودونforce.
- **96 Backend PASS و25 DOM PASS**، مع تحذيرAnyIOdeprecation قائم؛ PythonAST وJSsyntax وdiff checks ناجحة. هذه مجموعة GitHub المحددة لا كاملBackend. أضيفت13حالةBackend و4حالاتDOM إلى تغطية83/21 السابقة. حالات الملكية القديمة تستخدم صندوقًا اصطناعيًا وتستدعي send/verify الحقيقيين؛ حالات الاختراق الجديدة تستعمل API خامًا دون helper التأكيد التلقائي وتثبت الرفض. لا تُسقط assertions لحراس الملكية؛ عُدّلت fixture سابقة للرمز وselector checkbox الذي صار يسبقه inputOTP، وحالة race جهزت OTP قبل اختبار قيدDB.
- اختُبرت رسالة EmailMessage الفعلية الممررة إلى خدمة البريد الموجودة مع mock لحد الشبكة؛ لم ترسل Work رسالة حقيقية أو تستخدم بريد عميل أو token فعلي. لا يثبت ذلك إذن GitHubEmailRead أو تسليم Resend علىTEST.
- آخر نشر TEST مثبت بالسجل: Actions `40661043983`، job`122723844056`، `FULL_TEST_RELEASE_SUCCESS 1c7a4f643cda5b3dd65397a1973c2e2ea002a1db` بتاريخ28أكتوبر09:01UTC، مع `TEST_MIGRATION_GATE_PASSED`. آخرHEAD854 تحققCI فقط ولم يظهر نشرها في سجلActions الذي راجعناه.
- فحص أصل TEST العام `enhancements.js`: HTTP200، SHA256 `f3208be203f3501628d0c6421e11416d829c1f1da4b72f5a7d4608b7c9b1a58a` يطابق1c7a4f6 ولايطابق854. هذا دليل نسخة الواجهة، وليس قياسًا مباشرًا لـBackendPID/DB أو تعديلاتمشغّل خارجGit. لا نعيد تحقيقالبنية القديمة ولا نعدّلWorkflow.

| السيناريو | HTTP المحلي الفعلي / النتيجة | TEST الحقيقي لهذه الدفعة |
|---|---|---|
| A يربط GitHubA بعد الرمز | send200، verify200، confirm200 | BLOCKED؛ الحزمة غير منشورة |
| A يعمل Logout دونDisconnect | logout200/204؛ cookieA401؛ اتصالA يبقى | BLOCKED؛ لا قبول متعددالحسابات حي |
| B يفوض GitHubA بينما A متصل | send409 وconfirm409؛ لا بريد مرسل أو مستودعات | BLOCKED |
| C مستقل بلا اتصال / B يحاول مستودعاتA | API503 دون اتصال؛ direct foreign403/409 | BLOCKED؛ بياناتمصطنعة محلية فقط |
| A يفصل | تنظيفمحلي وGrant verified بمحاكاة204+404؛ لاUninstall | BLOCKED؛ لاGrantحقيقي منفذ |
| B يفوضGitHubA بعدفصلA دونرمز | confirm403؛ repositories503؛ رمزAالقديم400 | BLOCKED |
| نقل مقصود بعدالفصل معصندوقGitHubA | send200 إلىبريدGitHubA، wrong400، verify200، confirm200 ومعرفجديد | BLOCKED؛ يلزمصندوقمستقل مخول |
| بريدعام/غيرمتحقق/غيرمسموح/هويةمختلفة | 403/409/503؛ لاإرسال لبريدGatewayبديل | BLOCKED |
| فشلالبريد/تخمين/إعادةOAuth | 503صريح، ثم429؛ بعد5أخطاء400حتى لرمزصحيح | BLOCKED |
| بريدتغير بعدالرمز/انتهى/جلسةأخرى | 409/403/403؛ لااتصال | BLOCKED |
| تنظيفSecretsمنتهية وعداداتقديمة | يحذفالمحدد فقط ويُبقيUser/Project/التدقيقالآخر | BLOCKED لصيانةVPS |
| حفظ/Push/delete و73ساعة/Stash/فرعغيرمرفوع | اختباراتالقسم19 أُعيدتPASS ضمن96 | BLOCKED للنقلوالحذفالحقيقيين |

### 20.5 النشر المطلوب والعوائق الفعلية

لا يوجد اتصال SSH مهيأ لدى Work ولا أداة workflow_dispatch متاحة؛ لم ينفذ Work نسخة احتياطية أو restart أو deploy. لم تتوفر كذلك ثلاثة حسابات Gateway وحسابا GitHub مستقلان مخولان بمستودعات اصطناعية للقبول الحي، ولا وصول مستقل إلى صناديقهم لاختبار الرموز. هذه عوائق قبول فعلية، وليست مبررًا لتغيير البنية أو استعمال مستودعات المالك الخاصة أو إخفاء FAIL.

من مصدر TEST المثبت `1c7a4f6`، الحزمة المتوافقة **8 ملفات تشغيل**: `backend/app/main.py`, `backend/app/routes/github.py`, `backend/app/services/github.py`, `backend/app/services/workspace_cache.py`, `enhancements.js`, `dashboards.js`, `management.js`, `index.html`. لا migration جديد. يجب مراجعة preimages ونسخها ثم النشر اليدوي المنسق عبر الإجراء المعتمد؛ لا نشر لواجهة OTP وحدها أو Backend يفرض OTP أمام واجهة قديمة. يلزم فحص EmailRead ونجاح إرسال البريد فعليًا؛ لا تغيير لصلاحيات التطبيق أو config آليًا.

بعد النشر: A يربط مع OTP، ثم يخرج دون فصل؛ B يفوض GitHubA فيُرفض، ثم يربط GitHubB مع OTP؛ A يدخل ويفصل مع إثبات Grant، ثم يعيد الربط بمعرف جديد وOTP؛ وبعد الفصل يحاول B تفويض GitHubA دون رمز فيُرفض، ثم يُختبر النقل المقصود بالرمز المستقل. تتبعها حالات C والجلسة والحالات المنتهية والمستهلكة والمتوازية وفشل الحفظ والاحتفاظ بالملفات، بمحتوى مملوك فقط. سجل اختبارات المتصفح المشترك والمستقل وHTTP statuses وSHA المنشور دون codes/tokens/cookies. لا PASS نهائي قبل ذلك؛ ولا ادعاء منع شخص يملك جلسة GitHub وصندوق البريد معًا.


---

## 21. القرار التنفيذي النهائي — حالات GitHub الثلاث وخطة Silver/Gold اللاحقة (28 أكتوبر 2026)

**هذا القسم ينسخ جميع تعليمات GitHub السابقة التي تتعارض معه، بما فيها قاعدة القسم 20 التي كانت تفرض البريد/OTP على كل اتصال جديد.** تبقى الأقسام القديمة أدلة مؤرخة لفهم الأخطاء والاختبارات السابقة، **وليست تكليفات لإعادة بناء OAuth أو تغيير واجهة GitHub أو إعادة تنفيذ إصلاحات انتهت**. القاعدة: حافظ على المنجز، أصغر تعديل ضروري فقط، اختبر محليًا ثم TEST؛ لا تدّعِ أن السياسة الجديدة مطبّقة قبل توفر commit/نشر/قبول حقيقي يثبت ذلك.

### 21.1 تصنيف إلزامي لحالة GitHub بعد Callback، على الخادم

استخرج `github_user_id` الرقمي غير المتغير من GitHub `/user` بعد OAuth صحيح مرتبط بـGateway User/AuthSession وOAuth state وConnection ID. لا تعتمد على username أو البريد الذي يقدمه المتصفح ولا على حالة GitHub cookie. افحص الملكية النشطة أولًا، ثم سجل الارتباط التاريخي الموثوق؛ لا يسمح للواجهة باختيار سيناريو أو تمرير علم `first_time`. نفّذ الحراس كذلك في send/verify/confirm وواجهات GitHub الحساسة.

1. **اتصال أول على الإطلاق بهذه الهوية في Gateway، غير مرتبطة نشطًا بعميل آخر:** OAuth رسمي جديد، تحقق الجلسة والهوية والتثبيت والتأكيد الصريح، **بدون إدخال بريد يدوي أو OTP إضافي**؛ لا تعرض بريد GitHub. لا تُضعف الصلاحيات أو تتيح الوصول قبل confirm.
2. **هوية سبق أن اتصلت وفُصلت، سواء عاد نفس المستخدم أو مستخدم Gateway آخر:** OAuth جديد ومعرف اتصال وstate جديدان؛ يكتب العميل **بنفسه** البريد الأساسي المتحقق الخاص بحساب GitHub المختار، دون عرضه أو تلميحه ولو مقنعًا. يتحقق Gateway من تطابقه مع `/user/emails` (primary+verified) على الخادم؛ عند التطابق فقط يرسل رمز OTP إلى **ذلك البريد المتحقق من GitHub**، ثم يلزم نجاح التحقق والـconfirm. معرفة العنوان وحدها ليست إثبات ملكية. البريد المختلف لا يرسل رمزًا ولا يبيح الربط، والرسائل عامة لمنع تعداد البريد، مع تحديد المحاولات. لا رجوع لبريد تسجيل Gateway أو `/user.email` العام.
3. **هوية GitHub مرتبطة الآن بحساب Gateway آخر:** **ارفض الربط فورًا** (HTTP409 أو الحالة الملائمة) قبل إرسال رمز، ولا يسمح OTP أو التأكيد أو Callback المباشر بتجاوز ذلك. لا تفصل الحساب الأول أو تكشف اسمه/بريده. الرسالة بالعربية: «حساب GitHub هذا مرتبط حاليًا بحساب آخر في OpenCode Gateway، ولا يمكن ربطه بحسابين في الوقت نفسه. سجّل الدخول إلى حساب Gateway الذي يملك الاتصال وافصل GitHub أولًا، أو اختر حساب GitHub مختلفًا. تسجيل الخروج من Gateway وحده لا يفصل GitHub.» وترجمة إنجليزية مكافئة.

الترتيب **نشط لدى آخر → تاريخي منفصل → جديد** غير قابل للتجاوز. حساب Gateway مسجل الخروج ولكن لم يضغط Disconnect يبقى مالكًا نشطًا؛ تسجيل الخروج لا يلغي الاتصال. إذا كان نفس مستخدم Gateway متصلًا بالفعل، تعامل مع الربط القائم بدل إنشاء اتصال مكرر.

### 21.2 تذكر السابق دون إبقاء التفويض

القسم20 لا يحتفظ بتاريخ ملكية GitHub بعد Disconnect؛ لكي يميز القسم21 بين «أول مرة» و«سبق فُصل»، يحتاج إلى **علامة تاريخية محدودة بهوية GitHub الرقمية فقط** منفصلة عن الاتصال النشط والتوكن. افحص إمكانية إعادة استعمال سجل تدقيق موثوق قائم أولًا؛ إن لم يكفِ، صمّم أصغر تخزين آمن مع مدة احتفاظ وحق تصحيح/حذف وسياسة نقل/استعادة، وأي migration TEST لازمة. لا تترك revoked token أو OAuth state أو installation privilege أو connection secret، ولا تحوّل العلامة إلى قفل ملكية دائم أو تجعل حذف سجل تاريخي عشوائيًا يُخفّف الحماية. الحسابات التاريخية التي لا يمكن إثبات أنها جديدة **لا تُصنَّف آليًا «جديدة»**؛ وثّق استراتيجية انتقال آمنة وخصوصية متوازنة بدل تخمين.

### 21.3 الحفاظ على ما اكتمل

- احتفظ بالـOAuth session binding وConnection UUID الجديد وstate الأحادي وGitHub /user وownership checks وexplicit identity confirmation، وبإصلاح Callback Origin (e5d28b8)، ولا تعِد popups الفارغة.
- احتفظ بالفصل الصريح مع **Revoke Grant لمالك مُتحقق فقط** وتنظيف Gateway tokens/state/caches؛ لا Uninstall تلقائي لتنصيب قد يُشاركه آخرون، ولا تخلط logout مع Disconnect.
- احتفظ بـSave-before-delete والمراجعة قبل الحذف والتحقق من Push والـSHA البعيد، وعدم حذف ملفات غير محفوظة؛ احتفظ بحارس 73 ساعة للـStashes والفروع المحلية والملفات غير المتتبعة/ignored والمشاريع الداخلية والمحادثات. لا توسّع نطاق GitHub إلى Native/Preview.
- التصميم الحالي لبطاقة تأكيد الهوية معتمد وجيد؛ أضف حقل البريد والإرشادات فقط **في السيناريو 2**، وأخفِ أي OTP/Email controls في السيناريو 1، وأظهر منعًا واضحًا دون إرسال في السيناريو 3.
- `Email addresses: read` وصندوق إرسال فعلي مطلوبان **للسيناريو 2 فقط**؛ عدم توفرهما يمنع إعادة الربط التاريخي بأمان ولا يغيّر نتيجة أول ربط أصلي/منع الملكية النشطة. لا وعد بإجبار GitHub.com على طلب كلمة مرور جديدة أو محو cookies.

### 21.4 قبول GitHub قبل الانتقال إلى الاشتراكات

تغطية الاختبارات المحلية ثم TEST بثلاثة حسابات Gateway وهويتَي GitHub مستقلتين مخولتين على الأقل:
- جديد حقيقي → OAuth+confirm بدون OTP؛ تاريخي منفصل → بريد يدوي مطابق + رمز صحيح فقط؛ هوية نشطة لدى مستخدم آخر → منع بدون OTP.
- عودة صاحب الهوية بعد Disconnect، ومحاولة مستخدم آخر بعد Disconnect مع رمز صحيح/خاطئ، وخروج دون Disconnect؛ متصفح مشترك ومستقل؛ رد API مباشر/متوازٍ/منتهي ومكرر؛ رفض بريد غير مطابق ومنع enumeration والـrate limits.
- رفض مستودعات الغير؛ Grant revocation حقيقي ومطابقة هوية؛ حفظ/Push/تحقق/حذف نسخة مختارة فقط؛ حماية 73 ساعة؛ لا سرقة token أو إزالة تثبيت مشتركة.
- قبل إعلان PASS: SHA `updates`، SHA منشور على TEST، حالة `0028` وما بعدها إذا لزم، إرسال بريد حقيقي حين يُشترط، وسجل PASS/FAIL/BLOCKED. اختبارات96 Backend/25 DOM في القسم20 تخص **سياسة OTP لكل اتصال القديمة** ولا تُعَد اعتمادًا للسياسة الجديدة.

### 21.5 المرحلة المتبقية بعد قبول GitHub: صلاحيات Silver وGold

**هذه مرحلة منتج مستقلة قادمة وليست جزءًا من إصلاح OAuth ولا تغييرًا تجاريًا منشورًا.** مراجع المنتج التاريخية في القسم14 ما تزال مقترحات لا إعدادات: سقف **Silver 800 MB لكل مشروع** و**Gold 2 GB لكل مشروع**؛ والحد السابق في الكود لـGitHub worktree كان512 MiB، لذا لا يجوز ادعاء تفعيل الباقات. حدد أولًا حدود التخزين الإجمالية لكل حساب، وعدد المشاريع وWorkspaces النشطة، وحساب Git objects وbuild/cache والنسخ المؤقتة، وطريقة احتساب الاستهلاك وإدارة الامتيازات، وخطة التدرج عند بلوغ نحو50عميلًا وفق القياس.

خطوات المرحلة التالية بعد GitHub: (1) جرد نموذج الاشتراك/الدور والحصص الموجود في Python Gateway/PostgreSQL دون بناء موازٍ؛ (2) اقتراح مصفوفة امتيازات Silver/Gold وأثرها على الموارد وتكلفة Preview والـClone؛ (3) اعتماد قواعد الحساب والتخزين والعدد والرسائل؛ (4) تنفيذ حدود server-side ومعالجة الزيادة والانتقال بين الباقات دون فقد بيانات؛ (5) اختبار مستخدم فضي وآخر ذهبي وثالث غير مشترك على TEST، وقِس CPU/RAM/disk/network. **لا شراء VPS ولا تشغيل workers أو Shell/Preview غير معزول فقط لأن العميل Gold.**

### 21.6 ترتيب العمل وعدم الرجوع إلى المربع الأول

1. تعديل صغير للسيناريوهات الثلاث في `updates` مع اختبار؛ لا إعادة صياغة تدفق OAuth كليًا ولا العمل على أخطاء تاريخية مغلقة.
2. مراجعة التغيير ونشر منسق يدوي لـTEST بعد backup وpreimages وحماية البيانات؛ لا `master` أو LIVE أو Native أو Nginx/ports/shared services.
3. قبول GitHub الحقيقي أولًا ثم الانتقال إلى **تصميم صلاحيات Silver/Gold**، دون خلط المرحلتين.
4. يتقدم **القسم21** على البنود التنفيذية المتعارضة في الأقسام13–20؛ لا تحذف سجلات الإثبات التاريخية ولا تُحيل Work إلى مخططات قديمة على أنها سياسة حالية.

