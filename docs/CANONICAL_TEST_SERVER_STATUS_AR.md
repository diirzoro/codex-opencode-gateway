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
