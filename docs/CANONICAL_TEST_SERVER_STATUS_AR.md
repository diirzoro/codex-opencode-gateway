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
