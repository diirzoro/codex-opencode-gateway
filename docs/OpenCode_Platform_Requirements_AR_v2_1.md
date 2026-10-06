# وثيقة متطلبات منصة

# OpenCode Gateway

Hosted OpenCode. Your GitHub. Your AI.

منصة ويب لتشغيل OpenCode على مشروع GitHub أو مشروع جديد من الصفر داخل مساحة عمل مؤقتة وآمنة، مع حساب مستخدم، مزود AI يختاره المستخدم، جلسات متعددة على نفس المشروع، مراجعة للتغييرات، ثم Commit/Push إلى GitHub.

إعداد: طاهر عبيد حاج عبيد

الإصدار 2.1 — تحديث دورة إنشاء المشاريع وربط Workspace وOpenCode والجلسات





## المحتويات

- 1. الرؤية والهدف وحدود المنتج

- 2. الحالة الحالية الفعلية

- 3. القرار المعماري الأساسي

- 4. التقنيات المعتمدة

- 5. الإضافات الست عشرة المعتمدة

- 6. الصفحة العامة والتسجيل والمصادقة

- 7. ربط GitHub ودورة التوكن

- 8. مزود AI والنموذج وطريقة المصادقة

- 9. مساحة العمل والملفات والمحادثة

- 10. نموذج دمج OpenCode وعزل المستخدمين

- 11. دورة حياة المشروع وGit والـPush

- 12. المعاينة ورفع الملفات

- 13. الاستئناف والأحداث وحالات الـAgent

- 14. الموارد والاحتفاظ والتنظيف

- 15. الحساب والاشتراكات والدفع

- 16. لوحة الإدارة والبيانات الحقيقية

- 17. الأمان والشبكة والبيانات

- 18. نموذج البيانات والجداول

- 19. متغيرات البيئة والبنية التشغيلية

- 20. نطاق MVP وما ليس ضمنه

- 21. مراحل التنفيذ

- 22. شروط القبول النهائية

- 23. قرارات قبل الإطلاق

- 24. المراجع التقنية



## 1. الرؤية والهدف وحدود المنتج

الهدف هو تمكين المستخدم من العمل على مشروع GitHub من الهاتف أو الكمبيوتر عبر المتصفح، بدون تثبيت بيئة تطوير محلية وبدون رفع مشروعه إلى خادم المنصة كنسخة دائمة. GitHub يبقى المصدر الدائم للكود، بينما تستخدم المنصة مساحة عمل مؤقتة لتشغيل OpenCode وقراءة الملفات وتعديلها واختبارها ومراجعتها.

المسار الأساسي للمنتج:





## 2. الحالة الحالية الفعلية — 3 أكتوبر 2026





ملاحظة تشغيلية: ظهور No folders found في واجهة OpenCode الحالية متوقع لأن OpenCode معزول عن /home ولم يُنشئ Gateway بعد Workspace فعليًا. الحل المعتمد هو أن ينشئ Workspace Manager المساحة والملفات أولًا ثم يربط OpenCode بها، وليس إعادة فتح ملفات الخادم.

## 3. القرار المعماري الأساسي

- GitHub هو المصدر الدائم للكود؛ لا يُخزن source code في PostgreSQL ولا يُنسخ إلى مستودع مالك المنصة.

- كل جلسة عمل تحتاج Workspace على filesystem مؤقت، مع ownership واضح ومعرّف مستخدم ومعرّف جلسة.

- OpenCode يعمل على ملفات Workspace الحقيقية وليس على GitHub مباشرة.

- الـGateway هو نقطة الدخول الوحيدة للمستخدم؛ OpenCode نفسه يصبح خدمة داخلية قبل الإطلاق العام.

- عند نجاح Push والتحقق من commit البعيد يمكن تنظيف Workspace حسب سياسة الاحتفاظ.

- كل العمليات الحساسة — GitHub tokens، AI credentials، session ownership، workspace paths — تُحسم في الخادم وليس في المتصفح.

## 4. التقنيات المعتمدة

### 4.1 تقنية النسخة الحالية / MVP



### 4.2 ما لا نضيفه في MVP دون حاجة

لا Redis، لا Kubernetes، لا microservices متعددة، ولا queue منفصلة ما لم تظهر حاجة تشغيلية حقيقية. يبدأ المنتج بخدمة Gateway واحدة + PostgreSQL + OpenCode + Workspace Manager، ثم نفصل المهام الطويلة لاحقًا عند الحاجة.

### 4.3 المنافذ في بيئة التطوير الحالية





## 5. الإضافات الست عشرة المعتمدة

## 1. مصادقة مزود AI أوسع من API Key: دعم API key أو OAuth / device-code / login عندما يدعمه OpenCode أو المزود، وعدم افتراض أن كل المزودات تعمل بمفتاح فقط.

2. OpenCode Context منفصل لكل مستخدم/Workspace: عدم مشاركة HOME/config/data/state/cache أو auth بين المستخدمين. كل Workspace يمتلك سياق تشغيل مستقل أو معزول.

3. منع الهروب من جذر Workspace: File browser وOpenCode لا يعرضان ملفات الخادم. منع ../ والمسارات المطلقة وsymlink escape والوصول إلى /home و/etc وأسرار المضيف.

4. رفع ملفات وصور إلى المشروع: رفع آمن داخل Workspace مع حدود حجم ونوع، اسم تخزين مولد، metadata في PostgreSQL وحذف الملف مع Workspace.

## 5. دورة حياة GitHub credentials: GitHub App، installation id، short-lived tokens، إلغاء الربط، webhooks عند سحب الوصول، وعدم تخزين tokens في المتصفح.

6. سياسة الفروع: الافتراضي: work branch → review → commit → push → PR اختياري. لا force-push أو merge تلقائي إلى main.

7. حالات Agent حقيقية: Reading, Analyzing, Editing, Running command, Running tests, Waiting approval, Failed, Completed محفوظة في backend.

## 8. الاستئناف بعد انقطاع الاتصال: SSE/WebSocket بأرقام أحداث أو sequence IDs حتى يعاد الاتصال دون تكرار المهمة أو الفوترة.

## 9. حدود الموارد: CPU/RAM/disk/runtime/concurrency limits حسب الباقة، مع timeout واضح وقتل آمن للعمليات المعلقة.

10. PostgreSQL للـmetadata فقط: المستخدمون والجلسات والمحادثات والفوترة والـmetadata في DB؛ source code والملفات التنفيذية خارج PostgreSQL.

11. تصنيف المتطلبات حسب المرحلة: كل ميزة توسم MVP Required أو Phase 2 أو Future/Optional لمنع توسع غير منضبط.

12. Non-goals للنسخة الأولى: لا دعم لكل أنواع المشاريع، لا تعاون جماعي حي، لا قواعد إنتاج تلقائية، لا حفظ دائم للكود، ولا وعد بمزودات مجانية دائمة.

## 13. منع الإحصائيات الوهمية: لا تعرض لوحة الإدارة أرقامًا hardcoded كحقيقة؛ إما query حقيقي أو Not available yet/Preview.

14. Owner/Admin bootstrap وأدوار واضحة: Owner، Admin، Support، Finance، User، مع أقل صلاحية لازمة وسجل تدقيق، وإنشاء أول Owner بطريقة موثوقة.

15. OpenCode داخلي فقط قبل الإطلاق: لا وصول عام مباشر إلى 4096؛ كل طلب يمر عبر Gateway بعد التحقق من الهوية والملكية.

16. شروط قبول قابلة للاختبار: نجاح المنتج يقاس باختبارات end-to-end: مستخدم → GitHub → Workspace → OpenCode حقيقي → Diff → Push صحيح → Cleanup آمن.

## 6. الصفحة العامة والتسجيل والمصادقة

### 6.1 الصفحة العامة

- هوية OpenCode Gateway مستقلة مع توضيح أن OpenCode وGitHub خدمات خارجية وليست علاقة رسمية بالمنصة.

- شرح المسار الكامل بصريًا، الباقات عند اعتمادها، تجربة مجانية 10 أيام، FAQ، الخصوصية، الشروط، الدعم، العربية/الإنجليزية، RTL/LTR، Light/Dark، Responsive.

- التصفح العام متاح للزائر، لكن Workspace/Account/Admin/Onboarding المحمي يتطلب session حقيقية.

### 6.2 التسجيل والدخول

- الحقول: username، email، password، phone، country، postal/ZIP، region/city اختياريان.

- الدخول بالبريد أو username وكلمة المرور. Google/GitHub login يضافان فقط بعد تكامل حقيقي.

- الجلسة opaque random token، يخزن hash فقط في PostgreSQL، Cookie HttpOnly + SameSite=Strict، وSecure=true عند HTTPS.

- الـfrontend عند التحميل يستدعي GET /api/auth/me، ولا يعتمد على إخفاء الأزرار فقط.

- Admin يحتاج session + role=admin/owner على الخادم؛ غير المصرح له لا يرى البيانات حتى لو فتح رابط الصفحة.

## 7. ربط GitHub ودورة التوكن

- استخدام GitHub App أفضل من PAT عام، بصلاحيات repositories المختارة فقط.

- حفظ installation id وrepository identifiers والـmetadata في PostgreSQL، وليس raw token الدائم.

- استخراج short-lived installation token وقت الحاجة واستخدامه server-side فقط.

- عرض repos/branches المسموحة من API حقيقي؛ لا hardcoded project/branch في الواجهة.

- دعم private repositories ضمن الصلاحيات الممنوحة.

- عند revoke/uninstall webhook تُعلّم connection كمنتهية وتُوقف أي عملية جديدة وتتعامل بأمان مع Workspace مفتوح.

- لا يرسل token للمتصفح ولا إلى OpenCode logs أو agent prompt.

## 8. مزود AI والنموذج وطريقة المصادقة

- الفصل بين Provider وModel وAgent mode.

- تحميل قائمة providers/models من نسخة OpenCode المستخدمة أو API موثوق، لا قائمة ثابتة طويلة في frontend.

- دعم API key أو OAuth/device-code/اشتراك عندما يدعمه المزود/OpenCode.

- عند تخزين credential: تشفير server-side بمفتاح خارج قاعدة البيانات؛ إظهار آخر أحرف فقط؛ عدم إعادته كاملًا للواجهة.

- يمكن خيار session-only credential للعميل الذي لا يريد الحفظ.

- اختبار credential من الخادم دون إدخاله في logs.

- المجاني يظهر فقط إذا كان متاحًا فعليًا ولا يوصف بأنه ضمان دائم.

- فاتورة المنصة منفصلة عن فاتورة مزود AI؛ BYOK لا يعني أن المنصة تتحمل تكلفة API.

## 9. مساحة العمل والملفات والمحادثة

التخطيط المعتمد: sidebar للجلسات/المشاريع، الوسط للمحادثة والAgent، panel للمراجعة Files/Diff/Logs. على الهاتف تصبح Agent-first مع drawers/tabs بدل تصغير سطح المكتب.

- إنشاء Workspace بعد تحقق الحساب والاشتراك وGitHub permission.

- المسار المقترح: /var/lib/opencode-workspaces/{user_id}/{workspace_id}/repo

- نسخ الفرع المحدد shallow/partial clone عندما يناسب، مع التعامل مع LFS/submodules بوضوح.

- عرض اسم repo والbranch وbase commit SHA للمستخدم.

- File browser حقيقي مرتبط بالWorkspace فقط، ويعرض modified/added/deleted وdiff counts.

- لا تغيير branch مع تعديلات معلقة إلا بعد commit/stash/discard بقرار واضح.

- الأوامر الحساسة تحتاج approval داخل المحادثة قبل التنفيذ.

### 9.1 مصادر إنشاء المشروع

عند إنشاء Workspace جديد يجب أن يختار المستخدم أحد مصادر البداية التالية: GitHub Repository، Blank Project من الصفر، أو Template مدعوم مثل HTML/CSS/JS أو Python أو Node.js. لا يُجبر المستخدم على امتلاك repository جاهز قبل بدء العمل.

- GitHub Repository: يختار المستخدم repository وbranch مصرحًا بهما، ثم ينسخ Workspace Manager الفرع إلى مساحة مؤقتة مملوكة للمستخدم.

- Blank Project: ينشئ Workspace Manager مجلد repo فارغًا داخل مساحة المستخدم، ويهيئ Git محليًا عند الحاجة، ويمكن إضافة README/.gitignore ابتدائيين دون فرض هيكل مشروع.

- Template: ينشئ النظام ملفات بداية محدودة ومعروفة للـstack المختار، مع توضيح أن القالب نقطة بداية وليس بيئة إنتاج كاملة.

- يمكن للمشروع الجديد أن يبقى مؤقتًا أثناء العمل، ثم يُنشر لاحقًا إلى GitHub. إذا لم يملك التكامل صلاحية إنشاء repository جديد، يطلب النظام من المستخدم إنشاء/اختيار repository ثم ينفذ Push إليه.

### 9.2 الفرق بين Project وWorkspace وOpenCode Session

- Project: الكيان المنطقي الذي يراه المستخدم، وقد يكون مصدره GitHub أو Blank أو Template. يحتفظ بالاسم والمصدر والمرجع إلى GitHub عند توفره.

- Workspace: نسخة filesystem مؤقتة ومعزولة لمشروع واحد، لها owner واضح ومسار داخلي لا يُكشف للمتصفح.

- OpenCode Session: محادثة/تنفيذ Agent يعمل على Workspace موجود. إنشاء New Session لا ينشئ مشروعًا جديدًا ولا ينسخ الملفات من جديد؛ بل يبدأ جلسة جديدة على نفس ملفات المشروع.

- يمكن لـWorkspace واحد أن يحتوي عدة Sessions متتابعة مثل: بناء النسخة الأولى، إضافة Login، إصلاح الهاتف. كل Session ترى الحالة الحالية لنفس الملفات ما لم ينشئ المستخدم Workspace جديدًا.

### 9.3 فتح المشروع وإظهاره لـOpenCode

OpenCode لا يجب أن يبحث عشوائيًا داخل خادم VPS ولا أن يعرض مجلدات النظام. Gateway/Workspace Manager هو المسؤول عن إنشاء المسار الصحيح ثم تشغيل أو ربط OpenCode بذلك Workspace فقط.

المسار المستهدف يبقى مثل: /var/lib/opencode-workspaces/{user_id}/{workspace_id}/repo، ويُنشأ قبل إنشاء Session. إذا كان المجلد فارغًا فهذه حالة Blank Project صحيحة، وليست خطأ No folders found.

واجهة Gateway تعرض اسم المشروع والمصدر والbranch إن وجد، ولا تعرض المسار الحقيقي على Linux. الوصول إلى Files/Diff/Logs يأتي من Workspace الحقيقي عبر backend.

### 9.4 دورة New Project وNew Session

New Project → اختيار GitHub/Blank/Template → إنشاء Workspace → تجهيز الملفات → ربط OpenCode بالمسار → إنشاء أول Session → بدء Agent.

New Session → اختيار Project/Workspace موجود → إنشاء OpenCode Session جديدة → متابعة العمل على نفس الملفات دون إنشاء Workspace آخر.

## 10. نموذج دمج OpenCode وعزل المستخدمين

Gateway لا يفتح واجهة OpenCode العامة للمستخدم كبديل للمنتج. بل يستدعي OpenCode API/Server من backend ويوجه الجلسة إلى Workspace المملوك للمستخدم.

- إضافة OPENCODE_URL داخليًا مثل http://127.0.0.1:4096 في بيئة التطوير.

- Service layer واضحة: OpenCodeService لإنشاء/استئناف session وإرسال message وقراءة events/files/status حسب API المتاح.

- كل طلب إلى OpenCode يمر بعد require_user + workspace ownership check.

- عدم مشاركة auth.json أو DB/session state بين مستخدمين في الإطلاق العام.

- للإطلاق العام: process/container context مستقل لكل Workspace أو worker boundary لا يسمح بقراءة مساحات الآخرين.

- Gateway endpoint يعرض health/status الحقيقي؛ لا تظهر OpenCode Ready إلا إذا تحقق الخادم فعليًا.

### 10.1 نموذج تشغيل OpenCode لكل Workspace

في بيئة التطوير يمكن استخدام instance داخلي محدود، لكن قبل تعدد المستخدمين يجب ألا يعتمد النظام على OpenCode واحد مشترك بسياق filesystem/auth واحد.

- النموذج المستهدف: Workspace A → OpenCode context/process A، Workspace B → OpenCode context/process B، مع منافذ داخلية أو worker identifiers غير مكشوفة للعامة.

- كل instance/context يبدأ مع Workspace الخاص به كدليل عمل فعلي، ولا يملك صلاحية تصفح مساحة مستخدم آخر.

- OpenCode Web UI الأصلية على 4096 تبقى أداة اختبار/إدارة أثناء التطوير فقط؛ العميل النهائي يتعامل مع Gateway UI وGateway API.

- عند توقف أو حذف Workspace تُوقف عملية OpenCode التابعة له وتُمسح الأسرار والملفات المؤقتة وفق سياسة الاحتفاظ.

## 11. دورة حياة المشروع وGit والـPush

### 11.1 بدء الجلسة

بعد التحقق من المستخدم والاشتراك وصلاحية المستودع، ينشئ Workspace Manager مساحة معزولة، ينسخ branch ويحدد base SHA، ثم يبدأ OpenCode في هذا المسار فقط.

### 11.2 أثناء العمل

- يحفظ backend حالة task/conversation/events لإعادة الاتصال.

- كل Git command ينفذ باسم Workspace وليس بمجلدات المنصة.

- لا تنفذ Git hooks غير موثوقة تلقائيًا؛ submodules/SSH dependencies تحتاج سياسة واضحة.

- يوفر Restore Point أو patch عند الإمكان قبل تغييرات واسعة.

### 11.3 Review → Commit → Push

- المستخدم يرى Files/Diff/Logs/tests قبل commit.

- Commit يحتاج رسالة واضحة ويمكن أن ينشئ working branch تلقائيًا حسب السياسة.

- Push المباشر إلى main ليس الافتراضي؛ PR هو المسار الأكثر أمانًا عندما يناسب.

- لا force push تلقائي، ولا merge تلقائي من agent.

- إذا تغير remote branch منذ بدء الجلسة، تُكشف conflicts قبل push ولا يُخفى الفشل عن المستخدم.

- بعد push يتحقق Gateway أن expected commit موجود على GitHub وأن working tree نظيف قبل cleanup.

## 12. المعاينة ورفع الملفات

### 12.1 المعاينة

- المعاينة خاصة بالمستخدم، لا port عام دائم لكل مشروع.

- MVP يدعم نطاقًا معلنًا مثل static / Node / Python فقط، ولا يعد بتشغيل كل stack.

- المشاريع التي تحتاج DB تستخدم DB مؤقتة/اختبارية ولا تتصل بproduction تلقائيًا.

- عند الإطلاق بنطاق: preview origin منفصل وtoken قصير العمر/CSP حتى لا يسرق كود المشروع جلسة Gateway.

### 12.2 رفع الملفات

- رفع صور/ملفات إلى Workspace بعد المصادقة وownership check.

- حد للحجم وallowlist/denylist للأنواع الخطرة حسب الاستخدام.

- اسم داخلي مولد؛ original filename metadata فقط.

- منع path traversal والكتابة خارج repo/workspace.

- metadata: upload id, user id, workspace id, original name, stored path, mime, size, created_at.

- تحذف uploads المؤقتة مع Workspace أو حسب سياسة retention.

## 13. الاستئناف والأحداث وحالات الـAgent



- يحفظ كل event بترتيب sequence/event_id.

- SSE هو الخيار الأول لstreaming من الخادم للمتصفح؛ WebSocket يضاف إذا احتجنا تحكم ثنائي لحظي.

- عند reconnect يرسل العميل آخر event_id، والخادم يكمل من هناك بدل تكرار المهمة.

- إغلاق tab لا يساوي حذف Workspace أو إلغاء task تلقائيًا.

- زر Stop يرسل cancel حقيقي ويظهر النتيجة بوضوح.

## 14. الموارد والاحتفاظ والتنظيف

### 14.1 حدود الموارد

القيم النهائية تعتمد على مواصفات VPS والباقات، لكن يجب أن توجد حدود صريحة قبل تعدد المستخدمين.



### 14.2 سياسة الاحتفاظ

- Temporary session: cleanup بعد push مؤكد وإنهاء المستخدم.

- Resumable workspace: 14/30 يومًا حسب الباقة من آخر نشاط أو تاريخ محدد بوضوح.

- Countdown وتنبيه قبل expiry.

- إذا Push فشل أو الاشتراك انتهى: grace period لاسترداد العمل/patch، ولا حذف مفاجئ.

- Cleanup job يسجل الوقت والحالة والسبب فقط، لا يحتفظ بالكود في audit log.

## 15. الحساب والاشتراكات والدفع

- Account منفصل عن Workspace: profile، GitHub connection، provider settings، devices/sessions، language/theme، subscription/trial.

- التجربة المجانية 10 أيام من تفعيل الحساب، بسياسة تمنع تكرارها بطريقة بسيطة.

- كل Plan له version محفوظ: price, duration, runtime quota, storage, concurrent sessions, retention, features.

- تكلفة API الخارجية منفصلة. Usage platform قد يعتمد runtime/storage/quota معلنة.

- PayPal/Bank transfer لا تعتبر حقيقية حتى توجد integration/webhooks/storage للreceipts.

- Ledger مالي append-only نسبيًا: كل تعديل رصيد له سبب وفاعل ومرجع؛ webhook المكرر لا يزيد الرصيد مرتين.

- الأسعار النهائية لا تعتمد قبل قياس تكلفة التشغيل الفعلية.

## 16. لوحة الإدارة والبيانات الحقيقية

### 16.1 الأدوار



إنشاء أول Owner يتم عبر trusted bootstrap script/command على الخادم أو إجراء موثوق، وليس من نموذج التسجيل العام.

### 16.2 قاعدة البيانات الحقيقية فقط

- Registered/Active/Trial/Expired تُحسب من PostgreSQL queries الحقيقية.

- Payments/Revenue لا تظهر رقمًا إلا من ledger/payments الحقيقي.

- Visitors لا تظهر إلا إذا كان telemetry/analytics موجودًا ومعلنًا.

- OpenCode status يأتي من health endpoint الحقيقي.

- Sessions تأتي من workspace/session records الفعلية.

- أي metric غير منفذة تظهر Not available yet أو Preview ولا تستخدم أرقامًا مزيفة.

### 16.3 التشغيل والتدقيق

- عرض active workspaces, queue, CPU, RAM, disk, errors, failed clone/push/cleanup.

- إيقاف session مسيئة أو تجاوزت limits مع audit reason.

- Audit logs لإجراءات الإدارة والدفع والصلاحيات، دون أسرار أو source code.

- MFA/تحقق إضافي لحسابات Owner/Admin قبل الإطلاق التجاري.

## 17. الأمان والشبكة والبيانات

### 17.1 عزل التنفيذ

- Container/sandbox مستقل لكل Workspace في التشغيل العام، بلا root أو privileged.

- عدم ربط Docker socket داخل workspace.

- عدم mount لمجلدات host الحساسة.

- Network policy تمنع الوصول إلى PostgreSQL المنصة وmetadata services ولوحات الإدارة.

- المستودع غير موثوق: لا تُنفذ MCP/config/hooks/instructions منه بصلاحيات واسعة تلقائيًا.

### 17.2 حماية filesystem

- Workspace root هو الحد الأعلى لكل file API.

- رفض absolute paths و.. بعد canonicalization.

- فحص symlink target قبل القراءة والكتابة.

- عدم عرض /home/tahir أو .ssh أو .config أو OpenCode runtime الداخلي للمستخدم.

### 17.3 الأسرار

- تشفير provider credentials وGitHub secrets at rest بمفتاح منفصل عن DB.

- عدم logging للtokens/passwords/API keys.

- حقن credential فقط وقت العملية ومسحه/إبطال token عند انتهاء الجلسة.

- HTTPS إلزامي عند الإطلاق، rate limits ومحاولات دخول محدودة.

## 18. نموذج البيانات والجداول

PostgreSQL يخزن metadata وبيانات المنصة فقط. Source code، artifacts التنفيذية، وworkspaces تبقى في filesystem/object storage المؤقت حسب السياسة.



كل سجل مرتبط بالمستخدم/Workspace يحتاج ownership key وفهارس وقيود تمنع الوصول المتقاطع. Password hashes وsession token hashes فقط؛ لا plaintext passwords.

### 18.1 الكيانات الأساسية للمشاريع والمساحات والجلسات

- projects: id, user_id, name, source_type(github|blank|template), github_connection_id/repository_id عند توفره، default_branch، created_at.

- workspaces: id, project_id, user_id, local_path الداخلي، status، base_commit_sha، created_at، last_activity_at، expires_at، runtime/opencode reference.

- workspace_sessions: id, workspace_id, user_id, opencode_session_id، title/status، created_at، last_activity_at.

- لا يُعاد local_path الحقيقي إلى العميل؛ يستخدم backend workspace_id ويحل المسار داخليًا بعد ownership check.

### 18.2 واجهات Workspace Manager الأساسية

POST /api/workspaces لإنشاء Workspace من GitHub أو Blank أو Template.

GET /api/workspaces وGET /api/workspaces/{id} لعرض المساحات المملوكة للمستخدم فقط.

DELETE /api/workspaces/{id} لإنهاء/حذف Workspace وفق policy وبعد حماية العمل غير المرفوع.

POST /api/workspaces/{id}/sessions لإنشاء Session جديدة على Workspace موجود.

## 19. متغيرات البيئة والبنية التشغيلية

### 19.1 المتغيرات الأساسية



لا تُحفظ القيم الحقيقية في Git. .env يبقى 0600 ويستبعد من المستودع، وتستخدم .env.example بأسماء ومتغيرات دون أسرار.

### 19.2 البنية المستهدفة على VPS





## 20. نطاق MVP وما ليس ضمنه

### 20.1 MVP Required

- Register/Login/session حقيقي

- GitHub App وربط repo/branch حقيقي

- إنشاء مشروع من الصفر Blank Project وإنشاء مشروع من Template مدعوم، دون الحاجة إلى GitHub في لحظة البدء.

- Workspace Manager حقيقي ينشئ filesystem workspace ويعيد ربط OpenCode به بدل فتح OpenCode الخام.

- فصل New Project عن New Session؛ جلسات متعددة يمكنها العمل على نفس Workspace.

- Workspace واحد معزول لمستخدم واحد

- ربط OpenCode الحقيقي وإرسال prompt واستقبال events

- Files/Diff/Logs حقيقية

- Commit/Push إلى branch الصحيح والتحقق من النتيجة

- Basic account/trial

- Basic admin users/status الحقيقي

- Cleanup آمن بعد success

- Mobile usable flow

### 20.2 Phase 2

- Preview runner لمشاريع محددة

- Reconnect/resume متقدم

- Resource quotas/queue

- Retention tiers/grace period

- Full account devices/sessions

- Admin operational dashboard

- Activity/security logs

### 20.3 Future / Optional

- PayPal production integration

- Bank receipts workflow

- Wallet/ledger advanced

- Coupons/offers

- PR automation advanced

- More runtime stacks

- Team collaboration

- Advanced analytics

### 20.4 Non-goals للنسخة الأولى

- تشغيل كل أنواع المشاريع

- استضافة Git دائمة بدل GitHub

- فتح OpenCode الخام لكل مستخدم

- الوصول إلى production databases تلقائيًا

- Unlimited compute/storage

- Multi-user live collaboration في نفس Workspace

- ضمان استمرار أي provider/model مجاني

## 21. مراحل التنفيذ المحدثة

المرحلة 1 — إثبات المسار الحقيقي

Auth + GitHub App + repo/branch + Blank/Template project creation + Workspace Manager + isolated workspace + OpenCode API/runtime binding + real agent stream + multiple sessions per workspace + files/diff/logs + commit/push verified. هذه هي الأولوية الحالية قبل أي تجميل أو دفع متقدم.

المرحلة 2 — التشغيل الآمن والاستئناف

Container/sandbox isolation، resource limits، preview للstacks المدعومة، stop/reconnect، cleanup/retention، activity logs، account/admin الفعلي.

المرحلة 3 — التجارة والتوسع

Plan versions، payments/PayPal/bank، ledger، coupons، notifications، advanced reports، PR flows، قياس تكلفة التشغيل وتوسيع runtime stacks.

## 22. شروط القبول النهائية

1. الزائر يرى Landing ولا يستطيع فتح Workspace أو Account أو Admin دون session صحيحة.

2. لا يستطيع الزائر أو المستخدم فتح OpenCode على 4096 مباشرة في بيئة الإنتاج.

3. مستخدمان لا يستطيعان قراءة ملفات أو sessions أو credentials بعضهما.

4. اختيار repository وbranch يأتي من GitHub الحقيقي ويغير clone/workspace فعليًا.

5. الـbase commit SHA الظاهر يطابق GitHub وقت بدء العمل.

6. Prompt يصل إلى OpenCode الحقيقي وتظهر events حقيقية لا نصوص static.

7. Files/Diff/Logs تعكس filesystem/Git الحقيقي للWorkspace.

8. الأمر الحساس ينتظر approval ويستطيع المستخدم إيقاف task.

9. بعد انقطاع الاتصال يمكن العودة إلى نفس task دون تكرار التنفيذ.

10. Commit ينشأ في repo الصحيح، وPush يصل إلى branch الصحيح.

11. فشل Push أو conflict يمنع cleanup الذي قد يفقد العمل.

12. بعد Push ناجح يتحقق Gateway من remote commit ثم ينظف حسب policy.

13. لا يخرج file API من workspace root حتى مع ../ أو symlink.

14. GitHub/API credentials لا تظهر في browser storage أو logs أو DB بصيغة plaintext.

15. Admin metrics إما حقيقية من DB/runtime أو موصوفة بوضوح بأنها غير متاحة؛ لا أرقام وهمية.

16. تعديل plan مستقبلي لا يغير plan_version لاشتراك سابق، وwebhook دفع مكرر لا يكرر الرصيد.

17. يستطيع المستخدم إنشاء Blank Project دون GitHub، ويظهر Workspace حقيقي يمكن لـOpenCode قراءة ملفاته وإنشاء ملفات جديدة داخله.

18. يستطيع المستخدم إنشاء New Session على Project موجود دون إنشاء Workspace جديد أو فقد الملفات الحالية.

19. يستطيع المشروع الجديد الارتباط لاحقًا بـGitHub ثم Commit/Push إلى repository يختاره المستخدم ضمن الصلاحيات.

20. لا تظهر شاشة OpenCode الأصلية أو متصفح filesystem للمستخدم النهائي، ولا تعتمد المنصة على Add project اليدوي داخل OpenCode.

## 23. قرارات تحتاج تحديدًا قبل الإطلاق

- اسم النطاق النهائي.

- مواصفات VPS/worker capacity وعدد المستخدمين المتزامنين المتوقع.

- حدود CPU/RAM/disk/runtime لكل Plan.

- مدة retention/grace period.

- الstacks المدعومة في Preview.

- GitHub App permissions النهائية وWebhook URL.

- مزودات AI المسموح حفظ credentials لها ونوع المصادقة لكل مزود.

- الأسعار والحصص بعد قياس تكلفة التشغيل.

- حساب PayPal التجاري والبنك عند الوصول لمرحلة الدفع.

- سياسة الخصوصية وشروط الاستخدام وسياسة حذف البيانات.

## 24. المراجع التقنية

- OpenCode Server documentation: https://opencode.ai/docs/server

- OpenCode Providers documentation: https://opencode.ai/docs/providers

- GitHub Apps documentation: تُراجع عند تنفيذ GitHub App والصلاحيات والـinstallation tokens والwebhooks.

عند تنفيذ أي تكامل متغير أو حساس، يجب مراجعة الوثائق الرسمية الحالية وقت التنفيذ وعدم الاعتماد على افتراضات ثابتة داخل الواجهة.

## الخلاصة التنفيذية

الأولوية الحالية ليست إضافة مزيد من صفحات UI، بل إغلاق الفجوة بين الواجهة والبنية الحقيقية: حماية التنقل بالمصادقة، إنشاء Project من GitHub أو Blank أو Template، إنشاء Workspace معزول، ربط OpenCode فعليًا بمجلد Workspace، فصل Project/Workspace/Session، دعم New Session على نفس الملفات، تحويل Files/Diff/Logs إلى بيانات حقيقية، ثم Commit/Push والتحقق والتنظيف الآمن.