# المرجع المعماري الوحيد — OpenCode Native First
**قرار مالك أحدث: 29 أكتوبر 2026 | TEST وupdates فقط | حالة التطبيق: مطلوب تصحيح التنفيذ، وليس منجزًا**

## 1. قواعد المسؤوليات النهائية
- **Python/FastAPI/PostgreSQL: Control Plane فقط.** تسجيل الدخول والحسابات والخطط والحصص وملكية مشاريع/Workspaces وملفات العملاء ومراجعة الوصول وربط GitHub وأسراره والتدقيق. عند فتح Workspace يتحقق من العميل ويمنح صلاحية وصول محدودة النطاق. لا يكون Python محطة لمعالجة كل رسالة أو refresh للرسائل أو SSE أو providers أو models أو tools.
- **OpenCode Native 1.19.4: جهة الحقيقة والتنفيذ الحصرية** للمحادثات، الرسائل، تاريخ الجلسات، النماذج، المزودين، الوكلاء، الأدوات، القراءة/المعالجة، Todos، Questions، Permissions، Abort، SSE وNative storage/cache. لا Python AI engine أو queue أو proxy يدير الرد، ولا خدمة/عملية Native جديدة لكل Workspace، ولا OpenCode Web إضافي.
- **Nginx: نقل محمي إلى خدمة Native القائمة** بدون كشف Basic secrets أو raw Native endpoints للجمهور. نقل prompt وملف وstream لا يعبر Python كمنفذ معالجة المحتوى.
- **OS/file boundaries:** يجب إثبات العزل ومنع عميل من قراءة ملفات أو أسرار عميل آخر، ولا يكفي اختيار directory داخل Native مشترك كضمان أمني.

## 2. تصحيح التعارض مع المذكرة السابقة
المذكرة V3.9 القديمة تعتمد عمليًا: User → Python authorization في **كل طلب Native محمي** → Nginx internal redirect → Native. هذا وصف **للحالة القديمة لا للهدف النهائي الجديد**. قرار المالك الآن: يستخدم Python عند تسجيل الدخول وفتح Workspace وتغييرات الملكية والاشتراك، وليس على المسار الحرج للمحادثات وProvider/Model/Tools/SSE بعد فتح Workspace. لا تدّعِ أن المسار الحالي مطابق للقرار الجديد؛ لا تحذفه دون بديل أمني مكتمل.
  
**يلزم قبل التنفيذ تصميم آلية تخويل وصول مقيدة بالمستخدم وWorkspace والجلسة والعمليات والمدة، ويتحقق منها عند كل طلب دون استدعاء Python في المسار الحرج.** يجب إثبات إمكانية إبطال التفويض فور إلغاء العضوية/الصلاحية، وحماية cross-tenant وreplay وCSRF وسرقة الرموز وconfused deputy، وعدم تمكين اختيار directory أو Native credentials من المتصفح. التصميم البديل (Nginx/native auth adapter/قدرة موقعة) **لم يُعتمد أو يُنفذ بعد**؛ لا تفترض دعم Nginx للتحقق من JWT أو signature دون تركيب مدروس، ولا تفتح Native مباشرة لحل البطء. إذا تعذر ضمان هذا العزل، أبقِ مسار التفويض القديم مؤقتًا باعتباره BLOCKED، ولا تُضحِّ بالسلامة الأمنية.

## 3. العوائق والحالة
- المصدر الحالي: `native-session-client.js` يستخدم `/native-session/{workspace_id}/.../prompt_async`؛ `backend/app/routes/native_sessions.py` يقرأ ownership/Native metadata ويُرجع `X-Accel-Redirect` لـNginx؛ **Python لا يولّد الرد** لكنه لا يزال على مسار كل طلب.
- المذكرة V3.9 القديمة القسم13.1 حذّرت من metadata المتكرر و`usage_bytes()` ومسح `rglob('*')` في المسار الحرج. مطلوب قياس الأثر، وليس نسب كل البطء إليه.
- سجلات VPS 29 أكتوبر 08:02 UTC: كثير من `GET /api/native-test/workspaces/.../sessions` أعاد409، مع `prompt_async` واحد أعاد200. الأسباب الممكنة في `context()`: مشروع مؤرشف، جذر Workspace مفقود، إعدادات Native تحتاج مراجعة. **لم تُستخلص response bodies الحاسمة**. لا تعمم أن كل Native فشل، ولا تمس الملفات بحذف أو نقل.
- إصلاح مصدر `e1fa147bfe77` يخص false uncertain receipts وstale history؛ كان غير منشور وقت التوثيق. تأكيد SHA المنفذ على VPS مستقل عن GitHub HEAD.
- حدود shared Native credential store ومزودين متعددين وحماية tool execution لم يثبت قبولها الشامل. لا تتجاوزها بافتراض عزل directory.

## 4. قبول معماري ملزم
اختبارات old/new conversation، متعددة المستخدمين، Native prompt/provider/model/tools/file/SSE، سحب صلاحية لحظي، ملكية user→project→workspace→session، ملفات ومفاتيح منفصلة، معدلات latency وmetadata calls قبل/بعد. لا تغيير LIVE/master أو ports أو خدمة Native أو shared config. لا إعلان PASS من اختبار موك أو HTTP200 وحده.

## 5. حدود المستندات
هذا **المرجع الوحيد لقرارات المعمارية**. مذكرات فحص VPS لا تعيد تعريفها. المذكرة التاريخية `OPENCODE_GATEWAY_MASTER_SINGLE_MEMO_V3_9_2026-10-27_AR.md` تحفظ أدلة الماضي والإصلاحات وGitHub، لكنها لا تلغي قرار المالك الأحدث حول انتهاء Python من مسار المحادثة بعد فتح Workspace.
