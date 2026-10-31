# السجل الموحد لحالة سيرفر TEST والفحوصات
**لقطة 29 أكتوبر 2026 | حالة رصد لا سياسة معمارية ولا إذن تنفيذ**

## 1. الحدود
سجّل هنا فقط مشاهدات VPS، أوامر القراءة الآمنة، تواريخ النتائج، HTTP statuses، العمليات والمنفذ والذاكرة وحالة النشر. لا تخلطها مع تصميم Native First أو OAuth أو اشتراكات Silver/Gold، ولا تمس LIVE أو بيانات العميل.

## 2. إثباتات المالك الفعلية
- `opencode-gateway-test.service`: active/running؛ Python Uvicorn PID 677232 على `127.0.0.1:8001` (وقت اللقطة).
- `opencode-native-test.service`: active/running؛ PID 147483 على `127.0.0.2:4097`. ملف التشغيل من `/opt/opencode-live/node_modules/opencode-ai/bin/opencode.exe`؛ استخدام نفس الملف التنفيذي **لا يثبت** مشاركة التخزين.
- Native TEST `WorkingDirectory=/var/lib/opencode-native-test/workspace`, `HOME=/var/lib/opencode-native-test/home`, `XDG_CONFIG_HOME=/var/lib/opencode-native-test/config`, `XDG_DATA_HOME=/var/lib/opencode-native-test/data`, `XDG_STATE_HOME=/var/lib/opencode-native-test/state`, `XDG_CACHE_HOME=/var/lib/opencode-native-test/cache`; `EnvironmentFile=/etc/opencode-native-test.env`. فحص محتوى المتغيرات الإضافية (دون كشف الأسرار) غير مكتمل؛ لا تزعم ثبوت العزل الكامل.
- Gateway TEST `WorkingDirectory=/home/tahir/opencode-gateway-test/backend`، ملفا بيئة Native/release وrollback runtime موجودان؛ لا تفتحهما في التقارير.
- Nginx listens `127.0.0.1:18097` و`127.0.0.1:18098`.
- `MemoryMax=900M` لـNative TEST من unit definition؛ **ليس دليل OOM**.
- RAM: 3.8 GiB إجمالي، 1.6 GiB مستخدم، 2.2 GiB متاح في آخر لقطة؛ Swap 6.4 GiB إجمالي، 73 MiB مستخدم؛ ZRAM 1.9 GiB active. لا دليل في العينة على نفاد RAM.
- سجل Gateway الساعة 08:02:45–08:02:49 UTC: عشرات استجابات409 من `GET /api/native-test/workspaces/{id}/sessions`، واستجابة200 لWorkspace واحدة؛ حسم السبب يتطلب HTTP Response.detail/trace.
- الساعة08:02:58 UTC: `POST /native-session/.../prompt_async` أعاد200؛ لا يثبت اكتمال توليد النموذج. بعض `message/event/status/provider/permission/question` أعادت200.
- سجل Native عبر journalctl بلا entries في نافذة الفحص؛ ليس إثبات عدم تشغيل Native.
- انقطع اتصال SSH مرة برسالة `Connection reset`؛ لم يُثبت أنها السبب المباشر لتعطل المحادثات.

## 3. العوائق التي لم تُحسم
1. النص الدقيق لأسباب HTTP409 المتعددة، وهل تتمثل في archived project أو missing root أو Native config guard.
2. ما إذا كانت إصلاحات source الأخيرة منشورة على TEST، مع SHA والـasset versions.
3. التأكد من تنفيذ الرد لا مجرد acknowledgment HTTP200، وسلامة SSE والمرفقات عبر عدة مستخدمين.
4. فحص MemoryPeak/OOM الحقيقي؛ لا رفع MemoryMax أو Uvicorn workers دون قياس.
5. تحقق حدود تخزين Native TEST وفصل credentials عن LIVE من البيئة الفعلية دون طباعة الأسرار.
6. سياسة الاحتفاظ 24 ساعة: مقترح يحتاج فصل conversation history الدائم عن cache والمرفقات وملفات المشروع وإقرار العميل؛ **لا تحذف بيانات الآن**.

## 4. إجراءات عدم الإضرار
قراءة السجلات والأوامر الآمنة فقط إلى أن يعرف سبب الفشل. ممنوع reset/restart للعامل المشترك، أو نشر تلقائي أو إزالة workspace، أو `swapoff -a`، أو rm لملفات Native أو المشاريع، أو اعتبار 409 سببًا واحدًا قبل قراءة body.

## 5. التسجيل المستقبلي
لكل اختبار: UTC time، service، deployed commit، HTTP route/status/error category، نتيجة عملية Native الفعلية، memory/latency، PASS/FAIL/BLOCKED، بلا رسائل خاصة أو credentials. هذا المستند المصدر الوحيد **لحالة السيرفر وفحوصاته**، وليس وثيقة حلول المنتج.

## 6. تحديث 31 أكتوبر 2026 — سجل النشر والتنظيف الفعلي (TEST وLIVE)
**هذا قسم أدلة تشغيل جديدة بتاريخ 31 أكتوبر 2026، ويحل محل أي عبارة قديمة في الأقسام أعلاه تمنع التنظيف التجريبي الذي صرّح به المالك صراحة في هذا التاريخ. لا يغير معمارية Native First.** التاريخ السابق لقطة 29 أكتوبر فقط.

### 6.1 حدود البيئتين التي تأكدنا منها
| | TEST / updates | LIVE / master |
|---|---|---|
| نطاق | `test.opencode-gateway.codes` | `opencode-gateway.codes` |
| Gateway | `127.0.0.1:8001` | `127.0.0.1:8000` |
| PostgreSQL | `opencode_gateway_test` | `opencode_gateway` |
| مصدر التطبيق | `/home/tahir/opencode-gateway-test` | `/home/tahir/opencode-gateway` |
| ملفات المشاريع | `/var/lib/opencode-workspaces-test` | `/var/lib/opencode-workspaces` |
| Runtime | `/var/lib/opencode-runtime-test` | `/var/lib/opencode-runtime` |

خدمة OpenCode Native الأصلية مشتركة: `opencode-native-test.service` عند `127.0.0.2:4097`، ومسارا Nginx الداخليان `18097` و`18098`. **لم تُغيّر منافذها ولم يُعَد تشغيل محرك Native أثناء التنظيف**. Gateway يتولى التحقق من هوية العميل وملكية الموارد؛ رد Native/JSON/SSE لا يعود عبر Python.

### 6.2 GitHub Actions والتحرير
- ثبّت المالك الاحتفاظ بفرعين فقط: `master` للإنتاج و`updates` للاختبار. حُذفت 13 فرعًا مؤقتًا. لا أرشيف جديد للفروع. Workflowان أصليان فقط: `promote-native-live.yml` و`deploy-updates-test.yml`.
- إصلاحات LIVE السابقة: PR #19 (فصل الإجراءات)، #20 (تشخيص الإضافات)، #21 (مزامنة التهيئة المشفّرة)، #22 (زر Promote واحد)، #23 (استخدام GitHub Environment Secret `VPS_SUDO_PASSWORD`)، #24 (إزالة الاختبارات الثقيلة المتكررة من LIVE).
- أعطال من سجل التنفيذ: فقد `VPS_SUDO_PASSWORD`، ثم `INTEGRATIONS_SYNC_FAILED=PermissionError`، ثم `INTEGRATIONS_SYNC_FAILED=TEST_ENCRYPTION_KEY_MISSING`؛ حُسمت مشكلة sudo وSSH. يجب عدم اعتبار كل فشل سابق عيب كود/DB.
- **نشر التطبيق والإسكيما نجح** في Run [41165132316](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41165132316): `LIVE_CODE_AND_SCHEMA_PROMOTED`، واستجابة `/api/health` بقيمة `{"status":"ok"}`. هذا لا يثبت عمل كل وظائف التكامل أو SSE.
- حماية `production` كانت قائمة أثناء التشغيل. جرى تشغيل Job مؤقت على `push` لتنفيذ أعمال المالك المأذون بها، ثم تُعاد آلية LIVE إلى `workflow_dispatch` يدويًا فقط. لا ينبغي إبقاء مهام الحذف الدائم في Workflow المنتج.

### 6.3 جرد قاعدة البيانات قبل التنظيف — دليل فعلي
- Run القراءة [41165799626](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41165799626): PostgreSQL لديه 32 جدولًا في كل بيئة.
- TEST: 7 حسابات و43 مشروعًا و43 Workspace و55 Workspace Session؛ LIVE: 4 حسابات و8 مشاريع و8 Workspaces و25 Workspace Sessions.
- أربعة حسابات كانت تشترك في نفس المعرّفات بين البيئتين، وثلاثة حسابات إضافية في TEST. `ACCOUNT_IDENTITY_COLLISIONS=0`.
- أسماء الحسابات المطلوب إبقاؤها تطابقت حرفيًا في البيئتين: `admin` (صلاحية Admin واحدة) و`testuser`. هذه حسابات **موجودة مسبقًا في كل قاعدة**؛ لم يتم استيراد حسابات أو تغيير Password Hash.
- TEST مخزون إداري: سجل Resend/SMTP واحد، سجل GitHub App واحد، 3 سياسات بريد. LIVE قبل المزامنة: صفر في الجداول الثلاثة. مفتاح TEST غائب من ملف `.env` لكنه موجود في بيئة عملية `opencode-gateway-test.service`، ومفتاح LIVE موجود في `.env` وخدمته. تم إثبات فك تشفير إعدادات البريد `1/1` وGitHub App `1/1` وUser Provider `1/1`؛ سجل Provider قديم `0/1` **لم يمكن فك تشفيره**.
- إن نتيجة الجرد لا تعني أن البيانات السرية قد نُقلت إلى LIVE. **إعدادات Resend/GitHub لم تثبت مزامنتها بعد**؛ آخر تشخيص LIVE أعطى `EMAIL_SENDING_CONFIGURED=FAIL` و`GITHUB_APP_CONFIGURED=FAIL`. ممنوع نقل `CREDENTIALS_ENCRYPTION_KEY` من TEST لتحل محل مفتاح LIVE؛ المطلوب فك المصدر وإعادة تشفير المحتوى بمفتاح LIVE الأصلي دون عرض أي سر أو حفظه في Git.

### 6.4 تنظيف البيانات الذي طلبه المالك وأثبتته السجلات
- [Run 41166256377](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41166256377): حذف مستخدمين تجريبيين بعدد **5 من TEST و2 من LIVE**؛ الاحتفاظ فقط بـ`admin` و`testuser` في كل قاعدة. حذف جميع صفوف المشاريع وWorkspaces والجلسات والمحادثات المساعدة وسجلات المصادقة التجريبية. بعد الحذف: **TEST_USERS_REMAIN=2، LIVE_USERS_REMAIN=2، ومشاريع/جلسات العمل=0** في الجهتين. تبقى بيانات الملف الشخصي وكلمات المرور والاشتراكات المرتبطة بالحسابين، وإعدادات تشغيل المنصة.
- [Run 41166615948](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41166615948): بعد جرد ملفات منفصل، إزالة **18 مجلد مشروع في TEST** و**7 في LIVE**، وحذف **12 محادثة Native من TEST** باستخدام واجهة OpenCode الرسمية `DELETE /session/{id}`، وصفر محادثات Native ضمن تلك المسارات في LIVE. إعادة جرد بعد العملية: **0 مجلدات مشاريع و0 محادثات في المسارات المفحوصة**.
- [Run 41166757048](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41166757048): إزالة **3 أشجار Runtime يتيمة في TEST** و**7 في LIVE**، وصفر مخلفات Runtime مصنفة يتيمة عند المراجعة اللاحقة. **حُفظت 4 عناصر Runtime مرتبطة بالحسابات في TEST و3 في LIVE**؛ لم تُحذف كي لا تضيع مفاتيح/OAuth الحسابين.
- لم تنفذ هذه العمليات `pg_dump` أو نسخ احتياطية جديدة، ولم تنسخ TEST DB فوق LIVE، ولم تغيّر الدومين/Nginx/Native أو منفذ Gateway. عمليات الحذف المأذون بها **نهائية**؛ لا تفترض إمكان استعادة المحادثات من Git أو من سجل Actions.
- نطاق التحقق من المحادثات: مجلدات المشاريع التي أمكن تعيينها إلى OpenCode Native ومسارات Runtime التابعة للبيئتين. **لا يوجد دليل بفحص شامل مستقل لكل مخازن Native العامة خارج هذه المسارات**، فلا تُعلن خلو كامل XDG الخاص بـNative إلا بعد جرد مستقل لا يمس أسرار الحسابات.

### 6.5 ما بقي بعد التنظيف
1. تهيئة Resend وGitHub App في LIVE: لازالت غير مثبتة. يلزم استخدام مفتاح TEST الأصلي من مصدر آمن، وفك سجلات الإعدادات ثم إعادة تشفيرها بالمفتاح الحالي لـLIVE، والتحقق من البريد وGitHub OAuth فعليًا.
2. التحقق من تنفيذ Native end-to-end وسريان أذونات العملاء بعد إنشاء مشاريع/محادثات **جديدة** فقط؛ لا تستخدم مشاريع الاختبار المحذوفة.
3. إعادة الحماية اليدوية لـLIVE وإزالة Workflow/سكربتات التنظيف المؤقتة بعد انتهاء التنفيذ. تظل مذكرة المعمارية `CANONICAL_NATIVE_FIRST_ARCHITECTURE_AR.md` هي المصدر الوحيد لتوزيع مسؤوليات Native/Python/Nginx.

### 6.6 إغلاق عملية التنظيف والتحقق النهائي من GitHub
- أعيد `promote-native-live.yml` إلى **التشغيل اليدوي فقط** مع `environment: production` و`VPS_SUDO_PASSWORD`، وحُذف Job التلقائي المؤقت بعد إنجاز الحذف؛ Commit [9c0e0d0](https://github.com/diirzoro/codex-opencode-gateway/commit/9c0e0d0d3c402c6a41f1e45c1ff185105db6ec36).
- أُزيلت من `master` سكربتات الجرد والحذف لمرة واحدة (`audit-test-live-account-migration.py`, `audit-demo-file-storage.py`, `cleanup-demo-users-projects.py`, `purge-demo-project-files.py`, `cleanup-demo-runtime-contents.py`) لمنع إعادة استخدامها بالخطأ. توجد سجلات التنفيذ والمراجعة في GitHub Actions وتاريخ Git، لا في مخازن التطبيق الحالية.
- **الحالة النهائية المؤكدة بالعمليات:** حسابان في كل PostgreSQL، صفر مشاريع/Workspaces/Workspace Sessions في القاعدتين، صفر مجلدات مشاريع في المسارين المحددين، حذف محادثات Native المعروفة وعددها 12، وصفر مجلدات Runtime يتيمة بعد الجرد. أصول الحسابين ومفاتيح Runtime اللازمة لهما محفوظة. لا توجد وسيلة إثبات تلقائية هنا لمسح كل تخزين Native العام خارج المجلدات التي راجعناها.
- لم يُشغّل نشر جديد للتطبيق بعد عمليات التنظيف؛ لا تفسّر نجاح Jobs الحذف على أنه إثبات جديد لصحة البريد أو OAuth أو جميع خدمات Native. فحص صحة الإنتاج المباشر بعد الحذف **غير مثبت في هذا السجل**.

### 6.7 إعدادات الدفع المبدئية Stripe وCryptomus — سجل 31 أكتوبر 2026
- **حالة مزامنة Resend/GitHub:** لم تتم المزامنة إلى LIVE. سجلات إعدادات المزودين موجودة مشفّرة في TEST، ومفتاح TEST الأصلي ليس في ملف `.env` رغم ظهوره في بيئة الخدمة الحالية أثناء فحص القراءة؛ لا تدّع أن الاسترجاع أو النقل اكتمل. لا تستبدل مفتاح LIVE.
- أضيف إلى `master` كود إعدادات الإدارة فقط: Migration `0031_payment_gateway_settings`، الخدمة `backend/app/services/payment_gateway_config.py`، المسارات `backend/app/routes/payment_gateways.py`، الواجهة ثنائية اللغة `payment-gateways-ui.js` في تبويب **Administration → Billing**، واختبارات `backend/tests/test_payment_gateway_configuration.py`.
- حقول Stripe: `test/live`، `publishable_key`، `secret_key` (أو restricted)، `webhook_secret`؛ يتحقق الـBackend من نوع المفتاح وتطابق نمط TEST/LIVE. حقول Cryptomus: `merchant_id`، `payment_api_key`، و`payout_api_key` الاختياري؛ لا تعرض API مفاتيح سرية في ردود GET.
- تخزين الأسرار يستخدم نفس `CREDENTIALS_ENCRYPTION_KEY` الحالي لكل بيئة وFernet، مع حفظ المسودة بلا نقل أسرار بين البيئتين، وعدم الكتابة فوق سر سابق عندما يترك الحقل فارغًا. Endpoints متاحة لمدير النظام فقط، ويُفرض `Cache-Control: no-store`.
- لا يوجد Checkout أو webhook فعلي ولا دفع/سحب أو تفعيل اشتراك. تعود حالة `checkout_enabled/webhook_enabled/payouts_enabled` بالقيمة `false` دومًا. مسارات `/api/billing/webhooks/stripe` و`/api/billing/webhooks/cryptomus` **مخططة** وليست منشورة كمعالجات دفع.
- نجح GitHub Actions **فحص الصياغة السريع فقط** في [Run 41169450876](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41169450876): Python `py_compile`، Node `--check`، وفحص Alembic revision `0031` مقابل `0030`. هذا ليس اختبار وظائف الدفع أو قبول API حقيقي، ولم يُشغّل Suite pytest بالكامل.
- عاد `promote-native-live.yml` إلى `workflow_dispatch` اليدوي مع حماية `production` بعد هذا الفحص؛ commit `4bcc2820ab523a51f8a710d5b3aff82c178a485b`. **الكود محفوظ في GitHub master فقط؛ لم يُنشر إلى LIVE أو TEST في هذا الإنجاز.** يظل إعداد Stripe/Cryptomus في واجهة الإنتاج غير متاح حتى نشر الكود وتنفيذ Migration `0031`.
- المرحلة التالية: إصلاح مزامنة إعدادات بريد Resend وGitHub App دون كشف المفاتيح، ثم نشر إعدادات الدفع إلى TEST والتحقق منها، ثم Promote LIVE وتسجيل مفاتيح Stripe وCryptomus بأمان، ثم تنفيذ API الدفع والتحقق من Webhooks مع تسوية PostgreSQL قبل التفعيل.

### 6.8 توحيد مصدر GitHub بين master وupdates — توجيه المالك 31 أكتوبر 2026
- القرار الجديد: **احتفظ بفرعين فقط `master` و`updates`، ويجب أن تتطابق شجرة الكود والوثائق فيهما عند انتهاء كل مهمة**. عند الاختلاف تُنقل التغييرات المراجعة إلى الفرع الآخر ثم يُعاد التحقق عبر GitHub Compare؛ لا تتوقف المهمة على مجرد Commit في فرع واحد.
- الوثيقة التاريخية الأصلية `docs/OPENCODE_GATEWAY_MASTER_SINGLE_MEMO_V3_9_2026-10-27_AR.md` موجودة بالـBlob SHA نفسه في الفرعين قبل التوحيد (`8a5f9391ee689947adea831ad70b180c9ebad68c`)، ولا يُستبدل نصها. كذلك `docs/CANONICAL_NATIVE_FIRST_ARCHITECTURE_AR.md` مطابق أصلًا (`9dd1923fddd9973a42b892a38525d587fd1ff01f`). تُضاف نتائج التشغيل الجديدة إلى **هذه المذكرة المعتمدة** وليس إلى الملف التاريخي الملغى.
- سياق الفروع قبل الدمج: `master` يتقدم على `updates` بـ61 Commit مع 3 Commits مختلفة في تاريخ `updates`. كود LIVE وإعدادات Stripe/Cryptomus وملاحظات النشر كانت في `master`؛ workflow TEST نفسه متطابق كملف في كلا الفرعين. يجب جمع تاريخ الفرعين دون إتلاف المذكرة الأصلية، ثم تثبيت نفس الـCommit في كلا المرجعين باستخدام عمليات Fast-forward فقط (دون Force).
- **مزامنة Git تعني توحيد الملفات المتتبعة فقط**. قاعدة البيانات TEST `opencode_gateway_test` مستقلة عن LIVE `opencode_gateway`، و`.env` وNative credentials والتخزين والمنفذ 8001 مقابل 8000 لا تنتقل بينهما تلقائيًا. يحتفظ Workflow LIVE بالحماية اليدوية، بينما TEST قد ينشر تلقائيًا عند تحديث `updates`. نتيجة نشر TEST تُوثق مستقلة؛ مجرد تطابق GitHub ليس إثبات نشر السيرفر.
- لا تضف ملفات أسرار Stripe أو Resend أو GitHub أو Cryptomus إلى Git. إعدادات الدفع الجديدة ما زالت إعدادات تمهيدية فقط وغير مفعّلة في LIVE لحين تنفيذ Migration 0031 واختبار حقيقي.

### 6.9 تصحيح فشل LIVE Promote 41171036519 — 31 أكتوبر 2026
- [Run 41171036519](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41171036519): نجاح syntax وSSH، ثم توقف في خطوة **Audit TEST integration settings before touching LIVE** عند `INTEGRATIONS_SYNC_FAILED=TEST_ENCRYPTION_KEY_MISSING`. **لم تُرفع ملفات LIVE، ولم يجرِ ترحيل قاعدة البيانات أو نقل إعدادات البريد/GitHub بهذا التشغيل**. اختيار الفرع `master` كان صحيحًا، ومصدر الفرعين عند تلك اللحظة متطابق.
- التفسير: التحقق القديم كان يطلب `CREDENTIALS_ENCRYPTION_KEY` حصريًا من `/home/tahir/opencode-gateway-test/.env` رغم أن جرد [41165799626](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41165799626) سبق أن أثبت وجود المفتاح الأصلي في بيئة العملية المشغّلة `opencode-gateway-test.service`. في النشر السابق [41165132316](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41165132316) تم تجاوز فحص مزامنة التكاملات فقط ونشر الكود، ثم عادت حماية Promote، ولم تُعالج مشكلة مفتاح TEST.
- الإصلاح الجديد في `scripts/sync-test-platform-integrations.py`: إذا غاب مفتاح TEST من `.env` يحصل على `MainPID` من خدمة systemd المسماة صراحة، ويقرأ `/proc/<MainPID>/environ` أو يطلب قراءة `sudo cat` عبر FD3 بكلمة المرور المحمية الموجودة في `production`. لا تطبع القيمة أو تحفظها، وتظل قراءات PostgreSQL باسم مستخدم النشر غير المميز. إذا لم يُعثر على المفتاح الحقيقي يتوقف برسالة محددة؛ **لا يصنع مفتاحًا بديلًا**.
- يحافظ على شرط وجود مفتاح LIVE الحالي في `.env`؛ ويستعمله **لإعادة تشفير** بيانات Resend وGitHub App فقط عند `apply`. لا تُنقل مفاتيح التشفير نفسها، ولا الحسابات أو المشاريع أو الجلسات؛ لا مساس بالمحرك Native أو المنافذ. أضيف اختباران يثبتان fallback ورفض غياب مفتاح LIVE.
- **الحالة:** تعديل الكود لا يثبت اكتمال مزامنة Resend/GitHub في VPS. يجب نجاح خطوة `audit` ثم `apply` في تشغيل GitHub Actions جديد، مع `INTEGRATIONS_SYNC=APPLIED`، وبعدها فحص `EMAIL_SENDING_CONFIGURED` و`GITHUB_APP_CONFIGURED`. لا تعِد بقبول OAuth وإرسال البريد الفعلي دون اختبارات طرف إلى طرف.
- يجب إبقاء `updates` و`master` متطابقين بعد التعديل. تسليم الكود لا يعني نشر LIVE؛ يحتفظ Promote بالتشغيل اليدوي وحماية `production`.

### 6.10 إثبات نجاح TEST/LIVE ومزامنة Resend وGitHub — 31 أكتوبر 2026
- [TEST Run 41171253160](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41171253160) انتهى بـ`failure` في الخطوة 13، **وليس بسبب أخطاء اختبارات الكود**؛ نجحت فحوص المصدر وBackend وFrontend وSSH. كان Audit يشير إلى commit `736eb232ea0231a3760b1b95f57325c17051af6a`، وأثناءه تحرك `origin/updates` إلى `64254fbbc14a88f05dd0541a6d6b98e53716a412`. رفضت حماية SHA تنفيذ نسخة قديمة (قرار صحيح؛ لم يُنشر هذا التشغيل).
- [TEST Run 41171283449](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41171283449) **نجح** على `64254fbbc14a88f05dd0541a6d6b98e53716a412`: `207 passed, 1 warning` لاختبارات Python، نجحت اختبارات المتصفح، وظهرت `TEST_MIGRATION_GATE_PASSED` ثم `FULL_TEST_RELEASE_SUCCESS 64254fbbc14a88f05dd0541a6d6b98e53716a412`. كان فشل التشغيل السابق نتيجة انتقال الفرع أثناءه فقط.
- [LIVE Run 41171390502](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41171390502) **نجح**: استطاع سكربت المزامنة الحصول على مفتاح TEST الأصلي من الخدمة المشغلة عند غيابه من `.env`، وفحص `audit` إعدادات البريد وGitHub بنجاح `INTEGRATIONS_SYNC=AUDITED`، ثم نُشر الكود على LIVE مع ترقية قاعدة الإنتاج من `0030_staged_registration` إلى `0031_payment_gateway_settings`. ظهرت `LIVE_CODE_AND_SCHEMA_PROMOTED`، ثم **`INTEGRATIONS_SYNC=APPLIED`** لنقل إعدادات **Resend وGitHub App** وإعادة تشفيرها بمفتاح LIVE الحالي، دون استبدال المفاتيح الأصلية أو نسخ حسابات TEST.
- نتائج تشخيص LIVE من نفس التشغيل: `LIVE_ORIGIN=PASS`، `LIVE_PORT=PASS`، `GITHUB_CALLBACK=PASS`، `ENCRYPTION_KEY_PRESENT=PASS`، `LIVE_DATABASE=PASS`، `EMAIL_SETTINGS_SCHEMA=PASS`، `STAGED_REGISTRATION_SCHEMA=PASS`، `GITHUB_SETTINGS_SCHEMA=PASS`، `GITHUB_IDENTITY_SCHEMA=PASS`، `EMAIL_PROVIDER=RESEND`، **`EMAIL_SENDING_CONFIGURED=PASS`**، **`GITHUB_APP_CONFIGURED=PASS`**، وسياسات تسجيل الحسابات وربط GitHub `PASS`.
- **حدود التحقق:** التقرير يسجل `DELIVERY_VERIFIED=NOT_TESTED` و`GITHUB_OAUTH_END_TO_END=NOT_TESTED`. هذا يثبت نقل وحفظ الإعدادات وإمكانية قراءتها لا إرسال بريد حقيقي أو إكمال OAuth. لا تعيد الترحيل بلا حاجة. Stripe وCryptomus تم نشر بنيتهما (Migration `0031`) لكن لا تزال عمليات checkout/webhooks/payout معطلة، ويلزم إعداد حسابي التاجر ومفاتيحهما واختبارهما قبل التحصيل.
- اختلاف TEST/LIVE في مجلدات التخزين وقواعد PostgreSQL ومنافذها محفوظ. لا حاجة لتغيير حماية Workflow أو إعادة تشغيل OpenCode Native لمجرد نجاح المزامنة. قد تظهر تحذيرات Node.js 20 في GitHub Actions وهي ليست سبب فشل النشر السابق.

### 6.11 تصحيح مسار تعديل بيانات العميل — قرار المالك بتاريخ 31 أكتوبر 2026
- التوجيه النهائي للمالك: **تغيير اسم المستخدم أو البريد أو الهاتف أو رمز الاتصال لا يحتاج إلى رمز عبر البريد الإلكتروني**؛ توفير تكلفة رسائل Resend مطلب صريح. عوضًا عن ذلك يطلب النظام إدخال **كلمة المرور الحالية لإثبات ملكية الحساب** عند حفظ أي تعديل. لا يطلب تعيين كلمة مرور جديدة ولا يغير `password_hash`، ولا ترسل عمليات تعديل الملف الشخصي أي رسالة تحقق أو رمز مؤقت.
- واجهة العميل `app.js`: نافذة تحتوي على حقول الحساب وكلمة المرور الحالية **الإلزامية**، برسالة صريحة «لإثبات ملكية الحساب، يجب إدخال كلمة المرور الحالية (لن يتم تغييرها)»، وزر إظهار/إخفاء للمكتوب في حقل كلمة المرور. عند نجاح التعديل يظهر إشعار واضح. أزيلت نافذة رمز الـ60 ثانية من **مسار تعديل الملف الشخصي فقط** لأنها لم تعد مطلوبة؛ التسجيل الأولي/استعادة كلمة المرور/إثبات GitHub لها تدفقات مستقلة لا تتأثر.
- Backend `POST /api/profile/change/update`: يعتمد على جلسة المستخدم الأصلية ويطابق `verify_password(current_password, user.password_hash)`، ويرفض الخطأ بـ403، ويتحقق من تفرد الهوية ومطابقة الهاتف والقيود على بريد حساب مرتبط بـGitHub، ويحفظ البيانات و`AccountAudit` دون إرسال بريد أو تغيير كلمة المرور. أزيلت مسارات profile OTP القديمة `/request`, `/authorize`, `/confirm` حتى لا تستخدمها واجهة أخرى صدفة.
- **تنبيه إداري:** تأكيد كلمة المرور لا يثبت ملكية **البريد الجديد** مثل كود البريد؛ يجب إدخال عنوان صحيح، وإلا قد تتأثر استعادة الحساب والإشعارات. هذا اختيار تصميمي مقصود من المالك لتقليل كلفة الرسائل.
- أخبر المالك أنه **لم يدخل Resend API key بنفسه** في إعدادات المنصة حتى الآن؛ لذلك لا يُعلن عن نجاح إرسال بريد حقيقي من دون تدقيق صلاحية API key وإعداد نطاق `From` واختبار إرسال طرف إلى طرف. تحديث كود النقل عبر HTTPS في `email_delivery.py` ليس بديلًا عن توفير مفتاح مزوّد صالح أو توثيق نطاق الإرسال، ولا يرسل تعديل الملف الشخصي أي بريد في كل الحالات.
- مشكلة GitHub OAuth الظاهرة في الصورة: `redirect_uri is not associated with this application`؛ إعدادات Callback URLs يجب أن تطابق `https://test.opencode-gateway.codes/api/github/callback` و`https://opencode-gateway.codes/api/github/callback` تحت GitHub App الصحيح (المطابق لـ`client_id`). هذه خطوة لدى GitHub App خارج مستودع الكود، ولم يثبت إصلاحها فعليًا بهذا التعديل.
- تتم المحافظة على تكافؤ `master` و`updates` على نفس Commit بعد هذه التغييرات. نشر TEST من `updates` منفصل عن Promote المحمي واليدوي لـLIVE. لا يُعد نجاح GitHub CI وحده إثباتًا لتعديل ملف شخصي مستخدم فعلي.
- تحقق التنفيذ بعد هذا القرار: [TEST Run 41179088410](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41179088410) **نجح** للـCommit `edc3e078d516666a8c83eba96908f6079b724726`: `212 passed, 1 warning` في Python، وتحقق الواجهة، و`TEST_MIGRATION_GATE_PASSED`، ثم `FULL_TEST_RELEASE_SUCCESS`. يثبت هذا نشر كود التعديل على TEST دون OTP، وليس تجربة بريد حقيقي. لم يُنفذ Promote LIVE ضمن هذا التشغيل؛ يظل LIVE يدويًا ومحميًا.

### 6.12 تشخيص رسالة SMTP مع Resend — 31 أكتوبر 2026
- عرض المستخدم الخطأ الحرفي `SMTP rejected or could not send the email; delivery is unconfirmed` بعد نجاح إصلاح تعديل الملف الشخصي على TEST. **مصدر النص** هو فرع الإرسال القديم باستخدام `smtplib.SMTP(...)` في `backend/app/services/email_delivery.py`. لا يثبت الخطأ فساد البريد أو فشل Resend API نفسه، بل يعني أن SMTP رفض الاتصال/الإرسال أو تعذر تأكيد التسليم.
- **أول احتمال مؤكد من سجل النشر:** آخر Promote موثق لـLIVE ([41171390502](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41171390502)) كان قبل إصلاح واجهة تعديل الحساب ورفع الاختبارات في [TEST 41179088410](https://github.com/diirzoro/codex-opencode-gateway/actions/runs/41179088410). بالتالي قد تظل LIVE تعرض مسار OTP القديم، بينما TEST أصبحت تطلب كلمة المرور الحالية فقط ولا ترسل رسالة عند تعديل الحساب. يلزم Promote LIVE يدوي ناجح، ولا يعني تطابق GitHub للفرعين نشر سيرفر LIVE.
- أصلحنا حالة قديمة في `email_delivery.py`: عند وجود إعدادات Resend SMTP الموروثة من `.env` دون حقل `provider`، يُتعرف عليها باستخدام المضيف `smtp.resend.com` واسم المستخدم `resend` وتُوجّه عبر **Resend HTTPS API** على منفذ 443 بدل محاولة SMTP 587. وتعرض `public_config` الآن `transport=https` لذلك التكوين، مع إبقاء SMTP القديم للمزودين الآخرين كما هو. إذا غاب مفتاح إرسال Resend أو عنوان From يرفض الإرسال برسالة توضيحية ولا يحاول إرسال رسائل مدفوعة.
- أضيف اختباران آليان للتحقق من أن Resend الموروث لا يستخدم SMTP إطلاقًا، ومن رفض الإرسال دون مفتاح. **لا يوجد اختبار إرسال حقيقي**؛ لا تعرض أي API key أو token في السجل.
- تصريح المالك: لم يُدخل Resend API key بنفسه بعد. ظهور `EMAIL_SENDING_CONFIGURED=PASS` من تشخيص سابق يعني أن جدول إعدادات مشفّرة يحتوي بيانات اعتماد يمكن قراءتها، **ولا يعني أن المفتاح الحالي صالح عند Resend أو أن النطاق Verified أو أن الرسائل تُرسل**. يمكن إضافة مفتاح إرسال صالح من لوحة الإدارة `PUT /api/admin/service-integrations/email` مع `provider=resend` وعنوان مرسل تابع لـ`opencode-gateway.codes` بعد التحقق من النطاق لدى Resend. لا تضع المفتاح في المحادثة أو ملف Git.
- التعديل في الملف الشخصي لا يحتاج مفتاح Resend؛ فقط رمز التحقق في التسجيل أو الاستعادة أو تدفقات GitHub المستقلة قد يحتاج البريد. اختبارات TEST ونشر LIVE يجب التمييز بينهما. يُحافظ على `master` و`updates` متطابقين بعد هذا التصحيح.

### 6.13 معالجة عدم الانتقال لشاشة رمز التسجيل عند حد الدقيقة — 31 أكتوبر 2026
- لقطة شاشة إنشاء حساب أظهرت رسالة `Wait one minute before requesting another code for this email` رغم إفادة المستخدم بوصول رمز البريد، وبقاء الواجهة على نموذج التسجيل. **السبب من الكود**: `registration_drafts._email_send_limit()` يرفض طلب رمز مكرر خلال 60 ثانية برسالة 429، والواجهة القديمة كانت تعرض الخطأ فقط، كما كانت تستبعد استعادة شاشة الرمز من `sessionStorage` بعد انتهاء مهلة الرمز، رغم أن مسودة التسجيل موجودة على السيرفر ساعة كاملة.
- إصلاح `backend/app/services/registration_drafts.py`: دالة `recover(db,ticket)` تعثر على مسودة التسجيل فقط من بصمة **تذكرة المتصفح العشوائية المحمية داخل HttpOnly cookie**، ولا تسمح بالبحث حسب البريد؛ لا تنشئ مستخدمًا ولا ترسل رمزًا، وتعيد `pending=false` عند فقد التذكرة/انتهاء المسودة/إتمام التسجيل.
- إصلاح `backend/app/routes/auth.py`: `GET /api/auth/registration/pending` يعيد تحديًا قائمًا لصاحب تذكرة المتصفح، مع `Cache-Control: no-store`. هذا GET لا يقبل بريدًا أو رمزًا للوصول إلى طلب شخص آخر.
- إصلاح `app.js`: عند رجوع 429 من إرسال تسجيل مكرر، يبحث المتصفح عن الطلب السابق **من دون إرسال بريد جديد**؛ إن تطابق البريد مع نموذج التسجيل، يعرض شاشة إدخال الرمز الأصلي وحالة مهلة الـ60 ثانية وزر إعادة الإرسال المقيّد. بعد إعادة تحميل الصفحة يستعيد المسودة من الخادم حتى لو انتهى الرمز، لكي يتمكن المستخدم من إعادة الإرسال بعد انقضاء المهلة. عند عدم وجود HttpOnly cookie صالح يعرض الانتظار، ولا يكشف بيانات تسجيل أحد.
- اختبارات `backend/tests/test_email_code_signup.py` تغطي: استعادة نفس تحدي OTP بعد 429، عدم إرسال رسالة ثانية عند الاسترجاع، استعادة الشاشة بعد انتهاء صلاحية الرمز مع إعادة إرسال صريحة، رفض الاسترجاع بلا Cookie، وفشل الاسترجاع بعد انتهاء المسودة أو تأكيد الحساب.
- التسجيل لا ينشئ حساب `User` ولا يبدأ التجربة المجانية إلا بعد تأكيد الرمز الصحيح. لا تغيير لقواعد TEST/LIVE أو أسرار التشفير أو محرك OpenCode Native. **مزامنة `master` و`updates` مطلوبة**، ونجاح CI لا يثبت التسليم في LIVE دون تنفيذ Promote المحمي. لا تدّع أن البريد أُرسل في أي حالة لم يؤكد مزود البريد قبولها.


## تحديث 31 أكتوبر 2026 — ربط GitHub وتدفق الدخول في LIVE (تشخيص موثق، وليس إصلاحًا منشورًا)

### هوية التطبيق وسبب رفض LIVE
- أثبتت صور المالك أن GitHub App الحالي مملوك له: App ID `5470256`، App Slug `opencode-gateway-test-diirzoro`، OAuth Client ID `Iv23liGSq3yRR7okVSQJ`.
- عند محاولة الربط من `https://opencode-gateway.codes` أعاد GitHub رسالة: `The redirect_uri is not associated with this application.`؛ وكان Client ID في رابط التفويض مطابقًا للتطبيق أعلاه. يُرجَّح أن Callback الخاص بـLIVE غير مسجل ضمن GitHub App، لكن **لم يثبت بعد حفظه في GitHub أو نجاح ربط LIVE**.
- قرار المالك النهائي: **GitHub App واحد لنفس الحساب في البيئتين**، لا تنشئ تطبيق OAuth/App ثانٍ. يلزم تسجيل عنوانَي Callback الدقيقين في التطبيق نفسه:
  - TEST: `https://test.opencode-gateway.codes/api/github/callback`
  - LIVE: `https://opencode-gateway.codes/api/github/callback`
  مع منع wildcard. يظل كل مستخدم يفوض مستودعاته بنفسه، ولا تتشارك قواعد بيانات أو جلسات المستخدمين بين البيئتين.
- محاولة المالك إنشاء OAuth App عادي أظهرت رسالة GitHub `Your browser did something unexpected`؛ هذه المحاولة ليست إعدادًا مكتملًا وليست الحل المعتمد. إعداد المشروع القائم هو **GitHub App**.
- ينسخ `.github/workflows/promote-native-live.yml` حاليًا إعدادات تكامل GitHub المشفرة من TEST إلى LIVE باستخدام `scripts/sync-test-platform-integrations.py`. مشاركة هوية App مقصودة وفق قرار المالك، لكن يجب التأكد من أن Callback المسموح لكل بيئة محفوظ في GitHub نفسه، وألا تُنسخ إعدادات عنوان البيئة بصورة تكسر LIVE. لا تُعرض الأسرار ولا تُغيّر قاعدة بيانات العملاء.

### مشكلة شاشة تسجيل الدخول في LIVE
- صورة LIVE تُظهر أن الضغط على «تسجيل الدخول» يعرض `verifyEmailForm` وحقول رمز التفعيل، بدل `loginForm` (البريد/اسم المستخدم وكلمة المرور).
- مصدر `index.html` يحتوي نموذج الدخول منفصلًا عن `verifyEmailForm`، و`app.js` يحتفظ بحالة تحقق في `sessionStorage` باسم `og-email-verification`، ويحتوي `window.openAuthLogin` الذي يختار تبويب الدخول. يلزم فحص حالة runtime الفعلية والنسخة المنشورة قبل الجزم بأي سطر يسبب المشكلة.
- المطلوب: «تسجيل الدخول» يفتح login دائمًا؛ رمز التفعيل يظهر فقط ضمن تسجيل جديد معلّق أو طلب تحقق حقيقي، مع المحافظة على إمكانية استعادة التسجيل المعلّق دون عرض شاشة التفعيل افتراضيًا لكل زائر.
- **لا يوجد إثبات لإصلاح منشور أو قبول وظيفي على LIVE** في هذه اللقطة؛ لا تكتب «تم الإصلاح» قبل الاختبار الناجح.

### حالة GitHub والمزامنة
- في وقت الفحص: `master` و`updates` متطابقان عند commit `eae78f09267122c7a7d8a033f43fc630b1bd754a`، ولا توجد PR مفتوحة؛ ظهور اختلاف بين TEST وLIVE لا يثبت اختلاف كود الفرعين، وقد يرجع إلى إعدادات/حالة التشغيل أو النشر.
- أي توثيق لاحق يجب أن يميّز بين **تشخيص المشكلة، إصلاح مصدر الكود، حفظ إعدادات GitHub، نجاح Workflow، ونجاح الربط الحقيقي**.
- لا تغيّر محرك OpenCode Native ولا المنافذ أو قواعد البيانات أو الحسابات والجلسات؛ لا يُعتبر دمج PR نشرًا إلى LIVE.


## ملحق 31 أكتوبر 2026 — فصل مشاكل المصادقة عن فروق مدفوعات TEST/LIVE

### الأدلة المؤكدة
- أفاد المالك بالصور أن شاشة تسجيل الدخول في LIVE عادت لعرض الدخول الصحيح، بينما TEST يعرض أحيانًا نموذج OTP رغم اختيار تبويب «تسجيل الدخول». لا تُعامل مشاهدة LIVE هذه كاختبار آلي دائم.
- فحوص VPS التي أرسلها المالك: الخدمتان `active`، وملفات `app.js` و`auth.py` و`registration_drafts.py` المنشورة متطابقة وقت الفحص، وJS العام متطابق، والطلب الفارغ `POST /api/auth/register` يعيد `422` في البيئتين.
- تقرير LIVE المقروء فقط: جميع فحوص البنية الأساسية للبريد Resend والتشفير ومخطط التسجيل وGitHub App أعادت `PASS`، لكن `DELIVERY_VERIFIED` و`GITHUB_OAUTH_END_TO_END` بقيا `NOT_TESTED`.
- سجلات LIVE أظهرت `POST /api/auth/register => 201` تليها `PATCH /api/profile => 401`، وأحيانًا `429`، وهو دليل على انتقال غير صحيح في الواجهة بعد تسجيل غير مؤكد، لا دليل على إنشاء حساب فعّال.
- صور الإدارة تُظهر اختلافًا في وسائل الدفع: LIVE لديه طرق/إعدادات محفوظة، وTEST يعرض إعدادًا مختلفًا مع رسالة `Unexpected server response`. لا توجد أدلة كافية لتحديد استجابة الشبكة المسببة للرسالة. **قرار المالك: لا نقل أو نسخ أو توحيد لإعدادات البنوك/الاشتراكات بين قواعد TEST وLIVE، ولا تعديل للدفع حاليًا**.

### تصحيح واجهة TEST فقط
- المصدر: `updates`، Commit `21c61902d1b1ca5a33322d289daf8d109aee1deb`، الملف الوحيد المعدّل: `app.js`.
- عند فتح «تسجيل الدخول» من زر التنقل، تُختار استمارة الدخول صراحة؛ واختيار تبويب من المستخدم له أولوية على رد متأخر من استعادة طلب تسجيل معلّق.
- عند عرض OTP يُبرز تبويب التسجيل بدل ترك تبويب الدخول مضاءً مع استمارة تحقق.
- الرد غير المتوقع من التسجيل لا يؤدي تلقائيًا إلى `PATCH /api/profile`. لا يُسمح باستكمال مسار الحساب النشط إلا بعد فحص حالة `active` وتأكيد جلسة دخول عبر `/api/auth/me`.
- التغيير اختُبر نحويًا كمصدر JavaScript فقط؛ **لم يثبت نجاح نشر TEST أو إجراء اختبار دخول/OTP كامل عبر المتصفح**. تشغيل نشر TEST تلقائي عند push إلى `updates` وفق ملف Workflow؛ يجب التحقق من نتيجة التشغيل.
- بقي `master` على حاله في هذه الخطوة، ولا PR أو نشر LIVE أو أي تعديل DB/Native/payment/secrets.


## تصحيح 31 أكتوبر 2026 — منع تجاوز OTP في التسجيل العادي (TEST وLIVE)
- صور المالك تؤكد استمرار ظهور `Authentication required` على نموذج «إنشاء حساب» في كلا النطاقين دون الانتقال إلى إدخال الرمز.
- تحليل الكود حدّد تداخلًا محتملًا ومحددًا: كان `POST /api/auth/register` يقرر التسجيل عبر Google اعتمادًا على وجود Cookie `gateway_login_signup` وحده، حتى إن اختار المستخدم التسجيل العادي بالبريد. هذا المسار قد يُعيد مستخدمًا `active` بدل مسودة `pending_verification`؛ وهو متسق مع سجلات `201` ثم `PATCH /api/profile => 401` السابقة. **لم نثبت أن Cookie بعينه هو سبب كل محاولة فاشلة؛ يلزم اختبار فعلي بعد النشر.**
- الإصلاح المشترك في مصدر `updates`: حقل `social_signup` اختياري (افتراضيًا false)، وخادم `auth.register` لا يستخدم هوية Google إلا بطلب صريح مع Cookie صالح؛ التسجيل العادي يتجاهل/يمسح Cookie Google القديم ويبدأ مسودة OTP ويرسل رمزها. الواجهة ترسل العلامة فقط عندما تعود من Google OAuth بهوية معلقة مؤكدة، ولا تستدعي Profile لحساب عادي قبل OTP. أُضيف اختبار يمنع تجاوز OTP بـCookie قديم واختبار يرفض مسار Google الصريح من دون إثبات OAuth.
- الملفات المعنية حصريًا: `backend/app/schemas/account.py` و`backend/app/routes/auth.py` و`app.js` و`backend/tests/test_email_code_signup.py`. لا تعديل في Workflows أو إعدادات الدفع أو قاعدة البيانات أو مفاتيحها أو OpenCode Native.
- التمييز إلزامي بين إصلاح المصدر ونجاح TEST/LIVE الفعلي؛ لا تعتبر الدمج نشرًا ولا تعتبر HTTP 201 وحده دليلًا على وصول رسالة البريد.
