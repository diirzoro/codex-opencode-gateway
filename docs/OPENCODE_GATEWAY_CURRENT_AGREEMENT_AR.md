# OpenCode Gateway — الاتفاق التنفيذي الحالي (3 نوفمبر 2026)

## النطاق
- التطوير على فرع `updates` وبيئة TEST فقط. لا تعديل أو دمج `master` أو LIVE قبل نجاح اختبار TEST.
- نفس التصميم المستهدف للبيئتين، مع قاعدة PostgreSQL مستقلة لكل من `opencode_gateway_test` و`opencode_gateway`.
- لا إنشاء خدمات تشغيل AI بديلة أو قواعد بيانات AI إضافية.

## مسؤوليات النظام
- **OpenCode Native هو Data Plane الوحيد**: المزودون، النماذج، اعتماد المزود، اختيار الوكيل، الجلسات، الرسائل، `prompt_async`، SSE، الأدوات، الأسئلة، الموافقات، الإيقاف، المحفوظات.
- قاعدة البيانات المعتمدة التي ثبت أن عملية Native الجارية تستخدمها: `/var/lib/opencode-native-test/data/opencode/opencode.db`. لا قراءة/كتابة SQL مباشرة من Gateway داخل هذه القاعدة.
- فهرس المزودين والنماذج ليس مضمونًا في جداول SQLite: قراءة القائمة عبر `/config/providers` للمتصل/المهيّأ، و`/provider` للاكتشاف الكامل فقط عند الحاجة، عبر نفس محرك OpenCode المستمر. المفاتيح قد يحتفظ Native بها أيضًا في `auth.json` الأصلي.
- **Python ممنوع من تنفيذ AI**: لا قراءة نموذج/محادثة وتنفيذها في Python، لا نسخ catalog، لا queue/worker AI، ولا inference خارجي. Gateway المتبقي مسؤول فقط عن تسجيل الدخول والملكية والاشتراكات والمشاريع ومسارات الملفات المصرح بها. لا تلغِ عزل المستخدمين أو تفويض ملكية المشروع.
- Dashboard Connections يستخدم حالة Native الرسمية وحفظ/إلغاء الاعتماد عبر Native؛ Workspace يعرض النماذج المتاحة في حالة Native المخزنة، ويستعمل Native مباشرةً لتنفيذ المحادثات والأدوات والـSSE.
- منع تكرار تحميل `/provider` الكبير عند فتح كل Workspace. الحالة المؤقتة في ذاكرة واجهة المستخدم لا تمثل قاعدة بيانات إضافية، وتُلغى عند تبديل الحساب أو تعديل المزود.

## المنافذ المشاهدة (3 نوفمبر 2026)
- LIVE Gateway: `127.0.0.1:8000`
- TEST Gateway: `127.0.0.1:8001`
- Native الجاري: `127.0.0.2:4097`، PID عند الفحص `147483`
- Discovery proxy: `127.0.0.1:18097`
- Sessions/SSE proxy: `127.0.0.1:18098`
- لا اعتماد على `127.0.0.1:4097` أو مسارات V2 القديمة.

## تنفيذ تحقق على VPS
- إزالة تضمين V2 من TEST ونجاح `nginx -t` ثم reload.
- حذف `/etc/nginx/snippets/opencode-v2-test-locations.conf` ونجاح `nginx -t` بعد الحذف.
- حذف خمس قواعد OpenCode SQLite قديمة بحسب سجل المشغّل، مع الحفاظ على قاعدة Native النشطة وقاعدتي PostgreSQL للمشروع وقواعد أنظمة Linux/Docker.
- تلك العمليات تمت بأوامر شغّلها المالك، لا بواسطة أداة GitHub.

## تغييرات المصدر على updates بتاريخ 3 نوفمبر
- تعديل `app.js`: تحميل Workspace عبر `/config/providers` دون تنزيل `/provider` الكبير؛ fallback إلى Native `/provider` مرة واحدة فقط إن لم يعرض Nginx المسار الخفيف؛ Dashboard يعرض المزودين المهيّئين من Native بسرعة قبل بحث الفهرس الكامل.
- `native-session-client.js` يستخدم `prompt_async` وقراءة رسائل Native وSSE بالفعل، ولكن التحقق النهائي من مسارات Nginx المتاحة وتشغيل المحادثات والمزودين ما زال مطلوبًا.
- **تم التحقق عبر GitHub Actions**: نشر مسار `/config/providers` في Nginx TEST إلى `18098 -> 127.0.0.2:4097`، واختبارات بناء الواجهة والـpreflight نجحت. هذا لا يثبت بحد ذاته تجربة ربط مزود حقيقي أو SSE من حساب عميل.
- **تحسين لاحق**: Dashboard وWorkspace يستخدمان قراءة واحدة مشتركة في ذاكرة الواجهة لـ`/config/providers`؛ اختبار `tests/browser/test-native-provider-inventory.cjs` أصبح شرط نشر TEST.
- **تنظيف التنفيذ على TEST**: تم فك تركيب `agent.router` الخاص بالمحادثات والطوابير القديمة في Python، وتعطيل مهمة Python المجدولة لتحديث كتالوج Native وحذف محادثاته، وإخفاء أدوات تحديث كتالوج Native المكتوبة في Python وفك تركيب API الخاص بها. هذه تغييرات فرع `updates`؛ مخازن Native لم تُمس.
- **باقٍ قبل الدمج**: تجربة متصفح فعلية للمزود والمفتاح والنموذج و`prompt_async` وSSE والأدوات وإيقاف المحادثة، والتحقق من عزل المفاتيح بين حسابين، ومراجعة مسارات `/api/opencode/display-policy` بصفتها إعداد تحكم إداري لا مصدرًا لنماذج AI. ملفات محرك Python الستة حُذفت بالفعل من `updates` ونسخة TEST؛ يجب التحقق من دعم LIVE لمسار Native قبل الدمج.
- تغييرات GitHub في `updates` لا تثبت وحدها أن الكود نُشر أو أن LIVE تغيّر.

## قيود حرجة
- `/auth/{provider}` في Native 1.19.4 قد يكون ذا نطاق **العملية كلها**. تشغيل Native واحد لعدة حسابات لا يمنح تلقائيًا عزل المفاتيح؛ يمنع اعتبار الحسابات معزولة قبل اختبار ذلك. لا تعرض مفاتيح مستخدم آخر ولا تحذفها باسم عميل آخر.
- لم يتم الإذن بفتح Native للإنترنت بلا مصادقة؛ إلغاء ضوابط الهوية يعرض المفاتيح والمشاريع ويمنع اعتماد النشر النهائي.

## شرط الإغلاق
1. Native API للمزودين والنماذج والمفاتيح فقط، دون Python AI.
2. Dashboard يعرض المتصلين بسرعة، والبحث عن مزود إضافي عند الطلب.
3. Workspace يقرأ المتاح من Native دون استدعاء الفهرس الكامل لكل فتح.
4. إرسال رسالة عبر Native، SSE، history، stop، tools، وفتح Workspace مختلف، ثم اختبار حساب آخر.
5. CI ونشر TEST ناجحان، ومطابقة Nginx الواقع للكود؛ بعد ذلك فقط مراجعة دمج `master`/LIVE.

## تحديث تنفيذ 3 نوفمبر 2026 — حذف محرك Python القديم من المصدر

- **حُذفت فعليًا من فرع `updates`** الملفات: `backend/app/routes/agent.py`، `backend/app/services/message_queue.py`، `backend/app/services/opencode.py`، `backend/app/services/opencode_catalog.py`، `backend/app/services/account_provider_runtime.py`، `backend/app/services/session_recovery.py`.
- **أُزيل** تركيب `agent.router` نهائيًا من `backend/app/main.py`. لا يوجد مسار Python لتوليد ردود أو تشغيل queue في النسخة المحدثة؛ لا تحتفظ جلسات AI في PostgreSQL بوظيفة المحرك.
- **أضيف ملف `backend/app/services/native_control_bridge.py` فقط لقفل تغييرات ملفات المشاريع وإبقاء دورة حياة Gateway دون محرك AI**. لا ينشئ عمليات أو قاعدة بيانات أو cache، وتعيد واجهاته القديمة HTTP 410 بدل تشغيل نسخ OpenCode إضافية.
- **لم يتغير `master` أو عملية LIVE الجارية**؛ لكن عند نقل فرع `updates` إلى `master` مستقبلًا ستكون واجهات Python القديمة غير متاحة، ويجب إثبات تكامل Native في LIVE قبل الدمج.
- **التحقق**: نجحت GitHub Actions TEST على commit `39667647afd064f8c71c5dd77e26c5a3a063587d`، بما فيه فحوص مصدر TEST، واختبار عدم بقاء ملفات AI الستة، والنشر وصحة `/api/health`. لا يعتبر هذا بديلًا عن اختبار اتصال مفتاح فعلي، عزل حسابين، أو اكتمال محادثة Native مع SSE.
- **المتبقي**: إزالة تعليمات ومسارات الاعتماد القديمة الموجودة داخل وحدات إدارة Gateway التي لا تزال تحتوي شيفرة Legacy غير مركبة في TEST، والتحقق من كل استدعاءات Dashboard/Workspace، واختبار مستخدمين مستقلين قبل LIVE.


### تأكيد الحذف الفعلي على VPS TEST (نشر 3 نوفمبر 2026)
نجحت GitHub Actions run `41636803057` على commit `e71ebb16cf7d79246ce7863f6c2815da86d7658a`. أكدت سجلات التنفيذ `RETIRED_AI_FILES 6` ثم `DELETED_LEGACY_AI` لكل ملف من الملفات الستة أعلاه داخل `/home/tahir/opencode-gateway-test`. نجح `TEST_MIGRATION_GATE_PASSED` و`FULL_TEST_RELEASE_SUCCESS`، ولم تتغير عملية Native أو قواعد بياناتها بعملية الحذف. **هذه الأدلة تثبت إزالة الملفات الستة فقط، وليس اعتماد جميع النماذج أو سلامة مفاتيح المستخدمين أو نجاح محادثة AI فعلية.**


## تحقق مباشر من خدمة Native وإصلاح الاتصال والحذف (3 نوفمبر 2026)

- فحص GitHub Actions read-only رقم `41640486579` استخدم SSH + HTTP loopback إلى خدمة OpenCode Native الجارية، **دون Gateway/Python أو نموذج محاكاة**. `/provider` أعاد HTTP 200 و`/config/providers` أعاد HTTP 200.
- قائمة Native الكاملة: **235 مزودًا، و8,936 تعريف نموذج**. هذه تعريفات فهرس ولا تعني صلاحية كل نموذج للاستخدام. سجل Native نفسه أربعة معرفات في `connected`: `openai`, `google`, `deepseek`, `opencode`، لكن ذلك ليس إثبات مفتاح API ناجح أو ملكية حساب.
- `/config/providers` أعاد تعريفات `deepseek` (نموذجان) و`opencode` (9 نماذج). وعدد نماذج OpenCode ذات التكلفة الصفرية التي كشفها فهرس Native **9**.
- `/var/lib/opencode-native-test/data/opencode/auth.json` احتوى على معرفَي اعتماد **`openai` و`google` فقط**. لا يوجد إدخال `deepseek` أو `opencode` في هذا الملف. قد توجد اعتمادات من المتغيرات/إعدادات أخرى؛ لا يُستنتج من `connected` وحده وجود مفتاح.
- أُصلح في `app.js` افتراض أن كل تعريف في `/config/providers` يحمل مفتاحًا؛ تُعرض نماذج OpenCode المجانية دون مطالبة بمفتاح، ولا يُعتبر مرشح اتصال Native دليلًا على مفتاح صالح.
- أُصلح `DELETE /auth/{provider}` في TEST؛ نجاح الحذف يعتمد على إقرار Native نفسه، لا على اختفاء المعرف من `/provider.connected` الذي قد يبقى قديمًا في OpenCode 1.19.x. ويحجب المتصفح حالة المفاتيح التي أقر Native حذفها حتى لا يعرض اتصالًا وهميًا من الكاش.
- أُزيل اعتراض `409` المضلل عند ربط `deepseek` لمجرد وجوده في `connected`. إدخال/استبدال مفتاح فعلي ما زال يتطلب تأكيد المستخدم لأنه يكتب في مخزن Native المشترك؛ التحقق يعتمد على رسالة نموذج حقيقية.
- **لم تُحذف اعتمادا `openai` و`google` من مخزن Native المشترك**: قد يستخدمهما LIVE؛ لا يعتبر إصلاح زر الحذف حذفًا فعليًا لأي مفتاح. يتطلب الحذف الحقيقي إجراءً مباشرًا محددًا من المالك مع معرفة أثره.
- اختبارات الشيفرة ونشر TEST عبر Actions لا تحل محل تجربة `prompt_async` / SSE ونموذج مجاني فعلي، ولا اختبار حسابين لعزل الاعتماد؛ هذه شروط قبول باقية قبل `master`/LIVE.


## نتيجة اختبار المحادثة عبر Native (3 نوفمبر 2026)

- فحص `41641431421` أثبت أن Native يقدم تسعة معرفات مجانية أصلية، منها `opencode/beam-free` و`opencode/deepseek-v4.1-flash-free`؛ معرفات النموذج من HTTP Native وليست بيانات تجريبية من المشروع.
- اختبار `41641711601` أنشأ جلسة Native حقيقية ونجح `POST /session/{id}/prompt_async` لـ`opencode/beam-free`، لكن لم يتلقَّ رسالة مساعد خلال نحو 53 ثانية. لم يُعتبر نجاحًا للتوليد.
- اختبار `41642078622` أنشأ جلسة Native ثانية ونجح تسليم `prompt_async` لـ`opencode/deepseek-v4.1-flash-free`، لكن لم يتلق ردًا خلال نحو 41 ثانية؛ `GET /session/status` أظهر `retry` برسالة لم يُشخَّص سببها بعد. جرت محاولة إيقاف وحذف جلسة الاختبار في مهمة تنظيف السكربت.
- **الوضع الحالي**: الاستدعاء يصل إلى خدمة OpenCode Native الفعلية دون Python، لكن استجابة المزود المجاني غير مثبتة. لا تُعلن «المحادثات تعمل» أو «نماذج OpenCode متصلة فعليًا» قبل تشخيص سبب `retry` ونجاح رد حقيقي.
- حُذف افتراض أن `/config/providers` يثبت وجود مفاتيح؛ مؤشر `/provider.connected` قد يكون قديمًا ولا يدل على تخزين اعتماد صالح. `PUT /auth` لم يعد يرفض مفتاح DeepSeek لمجرد ظهوره في `connected`، لكنه يتطلب موافقة صريحة لأن مخزن Native مشترك.
- إصلاح `DELETE /auth` في TEST يستخدم إقرار Native، ولا يطلب اختفاء المزود من `/provider.connected` الذي قد يتأخر بسبب كاش OpenCode. واجهة Dashboard تميّز المزود المجاني عن المفتاح، وتعرض مزودي Auth الآخرين الذين لا تظهر تعريفاتهم في `/config/providers` لإدارة اعتمادهم.
- **اعتمادات `openai` و`google` الموجودة في `auth.json` لم تُحذف فعليًا** لاحتمال استخدامها من LIVE في نفس عملية Native؛ ولم تُحذف بيانات OpenCode الأصلية.


## نتائج الاختبار المحلي عبر Nginx + Playwright (4 نوفمبر 2026) — Windows، وضع `local`

**الهدف:** تشغيل Native محليًا بنفس توزيعة TEST (Nginx + X-Accel + منفذَي discovery/session)، ثم إصلاح ربط/حذف المفتاح واختبار رد حقيقي. كل التعديلات محلية على نسخة العمل (`updates` @ `08ea5b2`)، لم يُنفَّذ Git Push ولم يُمس TEST/LIVE/master.

### المعمارية المحلية الفعلية
- OpenCode Native (server) = `127.0.0.1:61339` (إصدار 1.19.5) — مصدر الحقيقة الوحيد.
- Gateway = `uvicorn` على `127.0.0.1:8180`، ووضع `OPENCODE_NATIVE_LOCAL_ENABLED=true`.
- Nginx محلي على `8080` (واجهة) + `19097` (discovery) + `19098` (session/auth) → Native، مع `@native_session_local`/`@native_discovery_local` و`/native-direct/api/*`.
- المسار: `Browser → Nginx 8080 → Gateway 8180 (تفويض) → X-Accel → Nginx 19097/19098 → Native 61339 → SSE مباشر`.

> ملاحظة: منفذَا `18097/18098` محجوزان من Windows (excluded range 18083–18182)، فاستُخدم `19097/19098` محليًا عبر `OPENCODE_NATIVE_LOCAL_DISCOVERY_URL`/`_SESSION_URL`؛ مسار TEST/LIVE يبقى `18097/18098` دون تغيير.

### الإصلاحات المنفَّذة (كود، قابلة للتراجع)
1. **`chat_attachments.py`** — إصلاح `import fcntl` (Unix-only) إلى قفل cross-platform (`msvcrt` على Windows)؛ فتح `/files` و`/git/status` (كانا 500).
2. **`native_sessions.py`** — وضع `local` في `deployment()` (دون شرط النطاق/DB) + `_native_ports()` لمنافذ قابلة للضبط + `state()` يعيد `native_account_directory` للوضع المحلي.
3. **`app.js` `nativeDirectTest`** — تعميم `active()`/`matches()` إلى الوضع المحلي (`nativeMode()`)، وجعل `defaultDirectory` ديناميكيًا (يقرأ `native_account_directory`).
4. **`native-session-client.js`** — ضبط `window.__nativeAccountDir` من حالة Native.
5. **`app.js nativeFailure`** — عرض رسالة الخطأ الفعلية من Native (بدل رسالة عامة).
6. **`management.js`** — تسمية زر الحذف إلى **«Delete API Key / حذف مفتاح API»**.

### نتائج Playwright الفعلية (PASS)
| الاختبار | النتيجة | الدليل |
|---|---|---|
| تحميل المزودين من Native | PASS | `GET /native-direct/api/provider → 200` (4 متصلون: deepseek/google/openai/opencode) |
| تحميل الوكلاء | PASS | `GET /native-direct/api/agent → 200` (Code/Plan) |
| إنشاء جلسة + prompt | PASS | `POST .../session/{id}/prompt_async → 204` |
| **رد نموذج حقيقي** | **PASS** | `deepseek/deepseek-v4-pro` → نص «مرحبا» (`error=False`) |
| ربط المزود عبر Native (إصلاح 422) | **PASS** | `PUT /native-direct/api/auth/anthropic → 200` ثم جلسة تحقق `prompt_async → 204` |
| تسمية زر الحذف | PASS | «حذف مفتاح API» في Connections |

### ما بقي (لم يُمس بسبب ملكية المفاتيح)
- **اختبار زر «حذف مفتاح API» الفعلي:** يحتاج اعتمادًا مستقلًا مملوكًا؛ مفاتيح `deepseek`/`openai`/`google` الحالية مشتركة مع عملية Native الجارية، ولم تُحذف. مسار الحذف مُثبت أنه `DELETE /auth/{provider}` عبر Native (`app.js nativeDirectTest.route` → `direct('auth/{id}',{method:'DELETE'})`).
- **التناقض المعروف:** ظهور مزود في قائمة `connected` لدى Native لا يثبت مفتاحًا صالحًا؛ واجهة Connections تعرض «مفتاح غير متحقق» بناءً على حالة Native، وسجل `account_audit` `:off` يبقى سجل فصل وليس دليل حذف مفتاح.
- Todo/Tools/Permissions، المرفقات، تكرار `/api/plans`، وحلقة إعادة المحاولة عند 410 — لم تُختبَر بعد.

## فصل كامل بين Python Gateway وOpenCode Native (4 نوفمبر 2026)

**قرار المالك:** Python Gateway للإدارة فقط (Login/Users/Projects/Workspace/Billing). كل وظائف OpenCode (نماذج/جلسات/رسائل/SSE/أدوات) يملكها OpenCode Native مباشرة عبر Nginx. لا تدخّل Python في OpenCode نهائيًا.

### الإصلاحات المنفّذة
1. **إزالة `require_model` من `_authorize_native`** (`native_sessions.py`): أُزيل استدعاء Python الذي يقرأ `/provider` ويتحقق من `connected`/`model in models` عند كل Prompt. تبقى فحوص السياسة (`provider_allowed`/`model_allowed`) كتحكم إداري فقط، ودقة النموذج الآن مسؤولية Native حصرًا (سيفشل طبيعيًا إذا كان النموذج غير صالح).
2. **منع استخدام 8180 كواجهة مستقلة** (`main.py` `browser_boundary`): أُضيف فحص Host يرفض أي طلب موجّه إلى منفذ Gateway (8180) بـ404، بينما يمر طلب Nginx (Host 8080) طبيعيًا. المدخل الوحيد للمستخدم هو `8080`، و`8180` يبقى خدمة Python داخلية للإدارة فقط.

### نتائج الاختبار (Playwright/HTTP)
| الفحص | النتيجة |
|---|---|
| `http://127.0.0.1:8080/api/health` | 200 (عبر Nginx) |
| `http://127.0.0.1:8180/api/health` | **404** (محجوب) |
| تسجيل الدخول عبر 8080 | 200 |
| Refresh يبقى على الصفحة | PASS (Connections تبقى Connections) |

### ملاحظة
- مسار Prompt/SSE يبقى عبر Nginx X-Accel-Redirect (Python يفوض الملكية فقط ثم Nginx ينفذ مباشرة). إزالة `_authorize_native` بالكامل تتطلب نقل تفويض الملكية إلى Nginx/رمز مسبق، وهو تحوّل أكبر مؤجل؛ الحالي يضمن عدم مرور بيانات Native عبر Python.

## إصلاح فصل حالة Workspace عن Native Session (4 نوفمبر 2026)

**الخلل المُشخَّص (مُعاد التحقق منه عبر Playwright):**
- بعد حذف محادثة (أو انتهاء جلسة الدخول)، كانت عمليات Workspace session تتحول إلى مسار TEST الثابت `/var/lib/opencode-workspaces-test/{owner}/{ws}/repo` بدل المسار المحلي، لأن `nativeDirectTest.active()` أُعمّم على الوضع المحلي، بينما `native-session-client.js` كان يقرأ `nativeDirectTest.active()` لاختيار النقل.
- النتيجة: قراءة قائمة الجلسات وإنشاؤها كانت تفشل أو تستعمل دليلًا غير موجود، فيبدو `activeWorkspace` معطّلًا ويتعذر إنشاء محادثة جديدة.

**الإصلاح (فصل النقل عن ربط المزود):**
- `app.js` `nativeDirectTest`: كشف `testHost` (TEST فقط) بجانب `active` (TEST+local لربط المزود)، وجعل `defaultDirectory` ديناميكيًا.
- `native-session-client.js`: استبدال كل `nativeDirectTest?.active()` بـ`nativeDirectTest?.testHost?.()` لعمليات نقل Workspace (session list/create/prompt/SSE/ملفات)، ليعود النقل المحلي إلى `/native-session/{ws}/*` و`/api/native-test/...` بدل مسار TEST الثابت.

**نتيجة Playwright:** استعادة Workspace تعيد المحادثة الكاملة (بما فيها رد `deepseek-v4-pro` «مرحبا»)، وزر «محادثة جديدة» مفعّل، وقائمة الجلسات تُقرأ عبر `/api/native-test/workspaces/{id}/sessions → 200`.

## تدقيق التنظيف المتبقي (7 نوفمبر 2026) — LOCAL فقط

**الهدف:** استكمال تنظيف ما تبقى بعد حذف محرك Python الستة، دون إعادة كتابة معمارية.

### ما اكتمل (تم الحذف/التصحيح فعليًا)
| المكوّن | النتيجة |
|---|---|
| `backend/app/services/native_catalog_maintenance.py` + مسارات `/api/admin/native/catalog-maintenance` الثلاثة | حُذفت (Python كان يجدول `models --refresh`؛ مخالفة معمارية، ومنكسر على Windows عبر `fcntl`) |
| مرجع `catalog-maintenance` داخل `_retired_test_data_route` في `main.py` | حُذف |
| `backend/app/routes/__init__.py` | أُفرغ إلى docstring (كان يستورد 4 وحدات فقط و`main.py` يستورد الكل مباشرة) |
| `enhancements.js` `renderWorkspaceEventLine`/`renderEventLine` | حُذف (ميت؛ `dashboards.js` يتجاوزه بعد التحميل) |
| اختبار `test_native_security_performance.py` المرتبط بالخدمة المحذوفة | أُزيل الاستيراد والاختبار |

### ما أُبقي عمدًا (متداخل مع مسارات فعّالة، ليس ميتًا)
- `providers.py` / `native_provider_accounts.py` / `runtime_snapshot.py` / `account_provider_sync.py` / `user_provider_credentials.py` / نموذج `ProviderCredential` — مستخدمة بمسارات **فعّالة** (`native_sessions.py` عبر `root`/`catalog`، مسار `/api/admin/native/providers`، عدّاد dashboard للاعتمادات). حذفها الكامل يتطلب هجرة مرحلية منفصلة (LIVE parity) وليس تنظيفًا موضعيًا.
- مسارات المزوّد/الفهرس القديمة في `workspaces.py` — متقاعدة في TEST عبر `_retired_test_data_route` + `browser_boundary` 410، ويستخدمها المتصفح عبر Native؛ إزالة المصدر الكامل مؤجلة لحين إثبات Native في LIVE.
- `tr()` المتكرر نطاقيًا و`uiCopy` و`openClientView` (نمط decorator مقصود) — لا خلل وظيفي؛ تُرك لتجنب إعادة هندسة غير ضرورية.

### حالة التحقق (LOCAL Windows)
- استيراد التطبيق ناجح: `239` مسارًا بعد الحذف.
- `node --check` سليم لـ`app.js`/`enhancements.js`/`dashboards.js`.
- `pytest backend/tests/test_native_security_performance.py`: `35 passed, 1 failed` — الفشل الوحيد سابق لعملي (`os.fwalk` غير موجود على Windows) ولا علاقة له بالتنظيف.
- **Playwright E2E عبر `:8080`: BLOCKED** — حزمة Nginx غير مثبتة على هذه الآلة وخدمة Native/Uvicorn غير قيد التشغيل حاليًا؛ لا يمكن تكرار اختبار المتصفح الكامل دون تشغيل الحزمة المحلية الكاملة.

### ما بقي (مؤجل/محجوب، بموافقة المالك عند الاكتمال)
1. هجرة مرحلية لحذف مسارات/خدمات المزوّد القديمة في `workspaces.py` بالكامل بعد إثبات Native في LIVE.
2. إعادة تشغيل الحزمة المحلية (Nginx 8080 + Gateway 8180 + Native) لإكمال اختبار Playwright الكامل (login/المشاريع/المحادثات/SSE/الأدوات/المرفقات).

## إصلاحات ونتائج فحص محلي إضافية (7 نوفمبر 2026) — تشغيل فعلي وPlaywright

شُغّلت الحزمة المحلية فعليًا (`opencode serve` 61339 + Nginx 8080/19097/19098 + uvicorn 8180) واختُبرت عبر Playwright على `127.0.0.1:8080`.

### السبب الجذري لتعطّل قسمي البريد وGitHub في الإدارة
- انكسرت مكتبة `cffi` داخل `.venv` (غياب `_cffi_backend` المترجم)، ما جعل `cryptography.fernet` يفشل → فشل تخزين/قراءة الاعتمادات المشفّرة → رفض حفظ مفتاح Resend وبيانات GitHub بالرسالة `503 Credential encryption dependency is unavailable`.
- **الإصلاح:** إعادة تثبيت `cffi` (أعاد `_cffi_backend`)؛ وثُبّت `pip` داخل venv عبر `ensurepip`. كما أُضيف `CREDENTIALS_ENCRYPTION_KEY` إلى `.env` المحلي (كان ناقصًا ويعطّل التشفير كلّيًا).

### أخطاء أخرى أُصلحت
- `index.html` نمط اسم المستخدم `[A-Za-z0-9_.-]+` يسبب `Invalid regular expression` في Chrome (وضع `v`) → صار `[A-Za-z0-9_.\-]+`.

### نتائج فحص Native المباشر (بدون مرور عبر Python)
| المسار | النتيجة | ملاحظة |
|---|---|---|
| `/native-direct/api/config/providers` | 200 · 82 KB · ~1.2s | قائمة خفيفة (Native مباشر) |
| `/native-direct/api/provider` | 200 · 7.29 MB · ~1.2s | الفهرس الكامل عند الطلب فقط |
| `/native-direct/api/agent` | 200 · 7 وكلاء | عبر Native مباشر |
| `/api/native-test/workspaces/{id}/sessions` | 200 | تفويض Python ثم X-Accel → Native |

### نتائج فحص البريد والتحقق (Playwright)
- حفظ مزوّد Resend في الإدارة → **200**، وتُخزَّن الاعتمادات مشفّرة في `email_delivery_settings` (رمز Fernet).
- إرسال البريد/التسجيل يصل إلى `api.resend.com` فعليًا. مع مفتاح اختبار وهمي أُعيد `401 Resend rejected the API key` — وهذا **يثبت صحة المسار** (التشفير + الإرسال يعملان؛ الرفض بسبب المفتاح الوهمي فقط).
- التسجيل لم يعد يفشل بـ«التشفير غير مهيّأ» أو «البريد غير متاح»؛ يصل الآن إلى محاولة الإرسال الحقيقية.

### حالة مفتاح Resend الحالي
- قاعدة البيانات المحلية تحوي حاليًا مفتاح الاختبار الوهمي الذي أدخلتُه للتحقق، **وليس** مفتاح المالك الحقيقي. يجب على المالك إدخال مفتاح Resend الحقيقي في الإدارة → «البريد والتحقق الإلكتروني» والضغط على «حفظ مزوّد الإرسال»، ثم يتفعّل إرسال رموز التحقق الفعلية.

## تصحيح المعمارية — صفر Python في عمليات OpenCode Native (7 نوفمبر 2026)

**البنية المعتمدة الوحيدة:** `Browser → Nginx → OpenCode Native`. لا يجوز لأي طلب OpenCode (مزوّدات/نماذج/وكلاء/جلسات/رسائل/SSE/أدوات/Todo/أسئلة/موافقات/ملفات/مرفقات) أن يمر عبر Python إطلاقًا — لا تفويض ولا تحقق ملكية ولا فحص سياسة ولا `X-Accel-Redirect` ولا قراءة كتالوج ولا proxy.

### الحالة الفعلية المؤكدة (فحص مباشر)
| الطبقة | الحالة |
|---|---|
| اكتشاف المزوّد/الوكيل/`config/providers` | **مباشر** عبر `/native-direct/api/*` → Nginx → Native (صفر Python) |
| الجلسات/الرسائل/الـSSE/الأدوات/Todo/الأسئلة/الموافقات | **تمر عبر Python** عبر `/native-session/*` و`/api/native-test/*` (تفويض + X-Accel) |

### مانع الأمان (BLOCKED)
- إصدار Native المركّب `1.18.31` عملية واحدة مشتركة بلا خيار عزل لكل مستخدم؛ `opencode serve` لا يقبل مفتاح عزل، و`auth.json` على مستوى العملية، ووسيط `directory` يُزوّده المتصفح ولا يُوثق به.
- **مُثبت:** `/native-direct/api/session?directory=<جذر مستخدم>` أعاد `200` مع جلسات المستخدم **دون أي تحقق** — أي أن التوجيه المباشر للجلسات يكشف جلسات المستخدمين لأي متصفح يعرف المسار.
- المرجع المعماري نفسه ينص: «`directory` وحده لا يكفي لعزل مستخدمين في Native مشترك».
- لذلك إزالة طبقة Python الحالية (وهي حد الأمان الوحيد حاليًا) ستعرض الجلسات والاعتمادات. **البنية المباشرة الكاملة محجوبة (BLOCKED) حتى توفّر عزل حقيقي.**

### المسار الصحيح (غير منفّذ بعد)
- تشغيل Native معزول لكل مستخدم: عملية `opencode serve` مستقلة بمسار بيانات مستقل عبر `XDG_DATA_HOME` (المتغير مدعوم في الإصدار المركّب)، مع ربط Nginx للمستخدم→مثيل Native الخاص به عبر هوية موثوقة.
- إلى حين ذلك يبقى الخادم محميًا ولا تُكشف جلسات/اعتمادات العملاء.

### نتائج العزل متعدد المستخدمين (مع طبقة الحماية الحالية)
- مستخدمان مستقلان (`testuser` و`localtest456`) اختُبرا عبر Playwright: محاولة الثاني سرد/قراءة/إرسال prompt إلى جلسة الأول → `404` بالكامل، وقائمة مساحات الثاني `0`. **عزل PASS مع الحماية الحالية؛ سينكسر بدونها.**

## تنفيذ الفصل — Python للجلسات/المشاريع فقط (7 نوفمبر 2026)

وفق توجيه المالك: **الجلسات والمشاريع فقط** تُدار/تُتحقق عبر Python (Platform)؛ وكل ما عداها من OpenCode يذهب **مباشرة** عبر Nginx إلى Native.

### ما نُفّذ فعليًا (LOCAL)
| المسار | التغيير |
|---|---|
| `nginx.conf` مسار `/native-direct/api/` | أُعيد فتحه للمرور المباشر، مع حجب `session` (القائمة/الإنشاء) فقط — يبقى في Python |
| `native-session-client.js` `url()/native()` | أصبحت تستخدم `/native-direct/api/*` المباشر في LOCAL (وليس `testHost` فقط) |
| `backend/app/routes/native_sessions.py` | حُذف مسار النقل `/native-session/{ws}/*` ودالّتا `transport`/`authorize_native`/`_authorize_native` بالكامل |

### النتيجة المؤكدة (Playwright على LOCAL)
| الفحص | النتيجة |
|---|---|
| قائمة الجلسات `/api/native-test/workspaces/{id}/sessions` | 200 · Python (تبقى) |
| المسار القديم `/native-session/{ws}/session/{id}/message` | **404** (أُزيل) |
| prompt مباشر `/native-direct/api/session/{id}/prompt_async` | 204 · عبر Native |
| رد النموذج الحقيقي | assistant «native» |
| message / todo / diff / permission / question (مباشر) | 200 |
| SSE `/native-direct/api/event` | 200 · `text/event-stream` |
| اكتشاف provider/agent/config/providers | 200 · مباشر |

### ملاحظة العزل (تبقى قائمة)
- التوجيه المباشر لا يفرض عزلًا لكل مستخدم (المسار `/native-direct/api/*` بلا مصادقة لكل متصفح، و`directory` يُزوّده المتصفح). قائمة الجلسات تبقى محمية عبر Python، لكن تنفيذ prompt على جلسة معروفة يبقى قابلًا للتوجيه المباشر دون تحقق ملكية.
- **العزل الحقيقي لكل مستخدم يتطلب Native معزولًا** (`XDG_DATA_HOME` لكل مستخدم + ربط Nginx بالهوية) — لم يُنفَّذ بعد وهو شرط إغلاق البند.

## اختبار وظيفي فعلي عبر Native (7 نوفمبر 2026) — Playwright مباشر

بعد الفصل (Python للجلسات/المشاريع فقط، وكل OpenCode مباشر عبر Nginx)، نُفّذت الاختبارات الوظيفية عبر Native الحقيقي:

| الوظيفة | النتيجة |
|---|---|
| رد نموذج حقيقي (`opencode/deepseek-v4.1-flash-free`) | PASS — «مرحبا/ok/native/direct» |
| أداة read (سرد الملفات) | PASS — أدرجت `.git/` `.gitignore` `README.md` `test_tool.txt` |
| أداة write (إنشاء ملف) | PASS — أنشأت `test_tool.txt` بالمحتوى «hello from tool execution» فعليًا على القرص |
| Todo إنشاء | PASS — 3 عناصر `pending` (review code / write tests / run build) |
| Todo دورة حياة | PASS — العنصر الأول انتقل `pending → completed` والبقية `pending` |
| SSE | PASS — `text/event-stream` مباشر |
| حالة الجلسة | PASS — `busy` أثناء التنفيذ ثم `idle` |
| استمرارية المحادثة بعد Refresh | PASS — الجلسة والـTodo محفوظة |
| اكتشاف المزوّد/النموذج | PASS — 235 مزوّدًا؛ connected = deepseek + opencode؛ 83 نموذجًا لـopencode |

### خلل مؤكد (باقٍ)
- مزوّد `deepseek` يظهر «متصل» لدى Native لكن بلا مفتاح فعلي في `auth.json` (يحتوي `opencode` فقط)، والطلب بـ`deepseek/deepseek-v4-pro` يعيد «Model not found». هذا تطابق مع ملاحظة المذكرة أن `connected` لا يثبت مفتاحًا صالحًا. الاستخدام العملي يعمل عبر `opencode` المجاني.

## إزالة نظام المحادثات المنفصل — مشروع واحد = محادثة واحدة (7 نوفمبر 2026)

**النموذج المعتمد:** `مشروع واحد = محادثة واحدة = جلسة Native واحدة دائمة`.

### ما نُفّذ
| الطبقة | التغيير |
|---|---|
| `native_sessions.py` | `POST/GET sessions` يعيد جلسة واحدة فقط لكل Workspace (إعادة استخدام الجلسة القائمة بدل إنشاء جلسة ثانية)، والعنوان يُشتق من اسم المشروع |
| `admin.py` | حُذف مسار `/api/admin/sessions` |
| `main.py` | قُسّم تقاعد المسارات: مسارات OpenCode (مزوّد/فهرس/جلسات) تُتقاعد في كل بيئة Native، بينما مسارات الملفات/Git تبقى Platform في LOCAL |
| `index.html` | حُذف زر «Sessions» من قائمة العميل، ولوحة `data-client-panel="sessions"`، ولوحة `data-admin-panel="sessions"`، وزر «New session» |
| `dashboards.js` | حُذف قسم «Recent conversations» من الرئيسية، وتبويب «Conversations»، وزر «New conversation» وقائمة المصادر، وأُضيف زر «+» (مشروع جديد) في قسم Workspace بالشريط الجانبي الأيسر مثل زر GitHub |
| `enhancements.js` | حُذف `loadAdminSessions` من `ADMIN_LOADERS` |

### التحقق (Playwright على LOCAL)
- إنشاء/فتح مشروع → جلسة واحدة فقط (`sessionCount: 1`)، و`POST sessions` يعيد نفس `runtime_id` دون إنشاء جلسة ثانية.
- الرئيسية: مشاريع فقط، لا قسم محادثات، ولا زر Sessions في القائمة.
- الإدارة: مسار `/api/admin/sessions` → 404.
- الشريط الجانبي الأيسر: زر «+» جديد في قسم Workspace (مشروع جديد) وزر GitHub.
- حُذفت أزرار/تبويبات المحادثات المنفصلة (Conversations/New session) نهائيًا، لا مجرد إخفاء.

### ملاحظات متبقية (غير معيقة)
- جلسات قديمة متعددة في مشاريع سابقة محفوظة في قاعدة البيانات لكنها لا تُعرض ولا يُعاد إنشاؤها؛ يُختار أحدث جلسة نشطة كالجلسة الوحيدة.
- العزل متعدد المستخدمين يبقى بند أمان منفصلًا مؤجلًا.

## حذف المشروع المحلي (7 نوفمبر 2026)

- أُزيل مانع «المشروع له محادثات» الذي كان يمنع حذف أي مشروع (لأن النموذج الجديد يمنح كل مشروع جلسة واحدة).
- حذف المشروع الآن يحذف معه سجلات الجلسة و`execution_events` ومساحة العمل والملفات، ويترك مستودع GitHub الأصلي دون مساس.
- إذا كان الوكيل ما زال يعمل (أو لديه أسئلة/موافقات معلّقة) يُعاد `409` برسالة واضحة: «الوكيل ما زال يعمل في هذا المشروع. أوقف المحادثة أولًا ثم احذف المشروع. / The agent is still working in this project. Stop the conversation first, then delete the project.»

### التحقق (Playwright)
- حذف مشروع `cache_expired` يحوي 3 جلسات قديمة → **200 deleted**.
- محاولة حذف مشروع والوكيل يعمل → **409** بالرسالة أعلاه.

## إزالة مسارات الاعتماد القديمة من Python وGateway DB (7 نوفمبر 2026)

**المطلوب:** اعتمادات المزوّدين تبقى في OpenCode Native (`auth.json`) فقط، وليس في قاعدة بيانات Gateway.

- عُمّم `_retired_test_data_route` في `main.py` ليطبق في كل بيئة Native (TEST/LOCAL/LIVE) بدل TEST فقط → أُزيلت مسارات Python القديمة للمزوّد/الفهرس/الجلسات (`/api/opencode/connections*`، `/catalog*`، `/api/workspaces/*/providers*`، `/runtime*`، `/sessions/*/messages*` …) من التوجيه في LOCAL أيضًا. عدد المسارات انخفض من 240 إلى **208**.
- حُذفت بيانات الاعتماد القديمة من قاعدة Gateway: `provider_credentials` (سجل واحد) و`user_provider_credentials`.
- النتيجة: ربط/حذف المزوّد يمر **مباشرة** عبر `/native-direct/api/auth/{id}` (Native)، ولا يكتب أي اعتماد في Gateway DB، ولا يعيد خطأ «Extra inputs are not permitted» (كان من مسار Python القديم الذي أُزيل).

### فحص Playwright بعد الإزالة
- `POST /api/opencode/connections/deepseek/credentials` (Python) → **404** (مُزال).
- `PUT /native-direct/api/auth/deepseek` (Native مباشر) → **200**.
- أداة read/write: أنشأت `test_tool.txt` فعليًا بمحتوى «hello from tool execution».
- دورة حياة Todo: إنشاء 3 عناصر وانتقال الأول `pending → completed`.
- Abort لجلسة busy → **200** وعادت الجلسة idle.
- (ملاحظة: اختباراتي أدخلت مفتاحَي «deepseek» وهميين في `auth.json` المحلي؛ يمكن للمالك حذفهما من Connections أو عبر `opencode auth logout`).
