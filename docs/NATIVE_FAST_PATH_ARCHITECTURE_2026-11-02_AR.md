# OpenCode Gateway — Native Fast Path / 2026-11-02

## الهدف
خدمات OpenCode Native هي مصدر الحقيقة للجلسات والمحادثات والأسئلة والأجوبة والوكلاء والمزودين والنماذج والأدوات وSSE. Python Gateway للهوية والملكية والحصص والتفويض فقط؛ لا يولّد أو ينفذ أو يجزّئ رد النموذج.

## الحالة التي كشفها فحص master
- يوجد تمرير فعلي إلى Nginx عبر X-Accel-Redirect، لكن Python تفحص body كاملًا وتطلب Native metadata قبل كل prompt_async.
- authorize_native قد ينتظر حتى 20 ثانية في worst case، وهي ميزانية زمنية وليست قياسًا للأداء.
- في الواجهة، takeComposerDraft يزيل نص المستخدم فورًا من الإدخال لكن لا ينشئ دائمًا فقاعة محادثة optimistic.
- post-send refreshSessionStatus وrefreshMessages كانا متتابعين؛ أصبحا متوازيين في commit 73ae2065.
- runtime-client.js يستخدم cache مع state validation؛ لا ينبغي استبداله باكتشاف مزودين حي في كل انتقال.
- للمشروع آليات صلاحيات Native للـ tools وملفات المستخدم؛ لا يجوز تجاوزها باسم السرعة.

## حدود المسؤوليات
1. Gateway/Python: تسجيل الدخول وتجديد/إبطال الجلسات، ربط workspace/user/project، ملكية native session، quota، permissions، سياسة المفاتيح وعزل الخدمات.
2. Native: إنشاء/عرض/تغيير/حذف الجلسات وفق API الرسمي، prompt_async، questions، permissions، agents/models، SSE، Todo، storage.
3. Nginx: transport مباشر للـ Native بعد تحقق موثوق؛ لا تعريض منفذ OpenCode المشترك للعملاء.
4. Client: تفاؤل ظهور الرسالة فور الضغط على إرسال (pending/accepted/failed/uncertain) دون إعادة إرسال تلقائية حال عدم التأكد، incremental SSE وتفادي refetch عند كل event.

## خطة عمل آمنة بالتسلسل
P0: قياسات request timing: UI click -> optimistic paint -> authorization -> Nginx forwarding -> Native accepted -> first SSE delta -> completion. التمييز بين cached metadata وuncached. لا تسجل محتوى prompts أو المفاتيح.
P1: إزالة تكرار fetch وتقديم cached workspace/session list فورًا، background revalidation، cancellation للانتقال السريع، dedup متزامن. امنع إعادة تحميل provider catalog لكل عرض.
P2: optimistic UI محلي بالـ messageID، reconcile مع Native receipt/SSE، حالات uncertain واضحة، لا إدعاء قبول قبل receipt.
P3: Native fast-path: authorization sidecar/NGINX auth_request بأقل وصول للـ DB، HTTP body يمر مباشرًا إلى OpenCode، وليس Python. **شرط أمني قبل التنفيذ**: مالك الجلسة، root path، صلاحيات الأدوات والملفات، model/provider entitlement كلها تُفرض على حدود الثقة؛ منع TOCTOU والتحويل بين المجلدات والمستخدمين، والحد من untrusted Native configuration وauthorization bypass. يجب اختبار معزول متعدد المستخدمين قبل استبدال مسار master.
P4: فهرس providers/agents/models يستخدم OpenCode native storage/cache، تحديث مجدول native مع state version؛ لا duplication في PostgreSQL ولا runtime provider discovery عبر الإنترنت عند كل فتح.
P5: اختبارات regressions: مستخدم A لا يرى أو يرسل لجلسات B، فشل auth / expired subscription، path traversal / symlinks / file://، aborted and uncertain prompts، session switch while streaming، concurrent sends، restart/rollback.

## ضوابط التشغيل
- لا توقف أو تعيد تثبيت OpenCode engine المشترك.
- لا تغير billing أو email أو GitHub auth أو بيانات المستخدمين.
- نشر master/LIVE فقط بعد قياس واختبارات multi-tenant ذات نتائج موثقة وخطة rollback.
- لا تدّعي سرعة أو اكتمال مسار مباشر لم يُختبر على الخادم.

## تحديث معماري مُلزم: Native Security First — 2026-11-02

يحل هذا القسم محل أي توصية قديمة تتعارض مع Native-first. لا يُزال نظام حماية قائم قبل إثبات بديل أقوى، ولا يعاد تصميم OpenCode كطبقة تنفيذ Python.

### إمكانات OpenCode الأصلية التي يجب استثمارها
- Native Sessions: إنشاء وعرض وحفظ الجلسات والرسائل وتبديل الوكلاء والنماذج والأسئلة والموافقات والبث SSE داخل OpenCode؛ لا طابور تنفيذ ولا محرك دردشة Python موازٍ.
- Native Permissions: قواعد allow / ask / deny على الأدوات والقراءة والتحرير والأوامر وexternal_directory، مع صلاحيات لكل وكيل وفق الإصدار المثبت؛ حظر الوصول خارج المشروع وتقييد subagents، وفحص symlinks والمسارات المطلقة.
- Native directory binding وNative session storage: ملكية الجلسة بمجلد العمل تُتحقق ضمن التفويض؛ OpenCode يبقى مصدر الحقيقة للمحادثة، ولا تحفظها Gateway مجددًا.
- Native provider/model/agent discovery and cache: استدعاء واجهات OpenCode ومخزنه الأصلي، لا اكتشاف إنترنت عند كل تبديل، ولا نسخة فهرس مزودين في PostgreSQL.
- مصادقة خادم OpenCode تحمي اتصال الخدمة فقط، لكنها **ليست** بحد ذاتها عزل multi-tenant أو إثبات ملكية جلسة لدى Gateway.

### المسار المختصر المطلوب
1. Gateway تتحقق من تسجيل الدخول والاشتراك وملكية المشروع ومساره، وتصدر تصريحًا قصير العمر محدد المستخدم والمشروع والجلسات والسياسة.
2. عند الانتقال إلى مشروع مختلف أو جلسة خارج التصريح، تعيد Gateway التفويض؛ التنقل بين الجلسات المملوكة ضمن النطاق يستخدم Native مباشرة.
3. داخل المشروع المصرح، المتصفح ↔ Nginx secure transport ↔ OpenCode Native للرسائل والردود وSSE والأدوات والوكلاء والنماذج؛ Python لا تقرأ نص prompt ولا تعالج response.
4. فحص الوصول خفيف لكل طلب عند الحد الأمني (token/scope/revocation)، دون Native metadata preflight الثقيل لكل سؤال؛ يجب الحفاظ على إبطال التصاريح عند إيقاف المستخدم أو انتهاء الاشتراك.
5. لا يُعطى المتصفح وصول عام لخادم OpenCode المشترك أو token المحرك؛ لا يسمح بتبديل session ID أو directory أو استدعاء route خارجي دون تحقق.

### العزل الفعلي المطلوب
إخفاء مشاريع الآخرين في الواجهة لا يكفي؛ permissions وdirectory binding ليستا sandbox بنظام التشغيل. يجب إثبات عزل نظام الملفات وأدوات Shell والـ subprocesses على مستوى عملية التشغيل/الحاوية أو وسائل مكافئة، بما يشمل symlink traversal وfile:// وsubagent والملفات المخفية. لا تعطيل للضوابط الحالية لمجرد تسريع الدردشة. تحقق من نسخة OpenCode الفعلية قبل الاعتماد على خاصية أمنية.

### تحسين الأداء بدون كسر الأمان
- قياس click→optimistic bubble، زمن التفويض، Native accepted، first SSE delta، فتح المشروع والجلسة، وعدد طلبات Python/Native لكل فعل دون تسجيل النصوص أو المفاتيح.
- عرض رسالة المستخدم فور الضغط على الإرسال بحالة pending، ثم reconciliation مع native receipt/SSE، وعدم auto-resend عند حالة uncertain.
- استخدام cached user/project scoped workspace/session lists، lazy-load، deduplicate concurrent requests، cancellation للطلبات القديمة، stale-while-revalidate مضبوط.
- تقليل polling وGET /message عند كل SSE event؛ incremental DOM بدل تحميل تاريخ المحادثة مع كل جزء.
- استدعاء Native providers/models/agents من مخزنه cached/versioned فقط عند الحاجة؛ refresh دوري مدروس دون restart للمحرك.
- نقل فحوص التفويض المكلفة خارج مسار كل prompt بعد بناء بوابة وصول وعزل يحققان متطلبات الأمان ويجتازان اختبارات متعددة المستخدمين.
- الاختبارات إلزامية: مستخدمان A/B، ID swap، cross-project access، path escape، shell، file URI، subagents، agent/model switch، session changes during SSE، revoke and concurrent sends.
- قبل LIVE: أرقام baseline وp50/p95 وتحسن ملموس، اختبارات regression، وrollback؛ لا إعادة تثبيت أو إعادة ضبط OpenCode المشترك.

### تصحيح البنود القديمة
- أي بند يوحي بأن Python يجب أن يفحص محتوى كل prompt أو يجلب Native session/tool metadata في كل إرسال هو **مرحلة انتقالية حالية**، وليس هدفًا معماريًا نهائيًا.
- أي بند يسمح بوصول مباشر غير مفوّض إلى المحرك المشترك مرفوض.
- لا إعادة ابتكار إدارة الجلسات أو محرك البث أو فهرس المزودين داخل Gateway.
- لا تغيير لخدمات البريد أو الدفع أو GitHub أو أسرار العملاء ضمن هذا المسار.

## قرار نهائي: لا خدمات جديدة — OpenCode Native فقط (2026-11-02)
- ممنوع إنشاء أي محرك أو خدمة إضافية للمحادثة أو الجلسات أو نماذج الذكاء أو المزودين أو الأدوات أو تخزينها أو تشغيلها أو بثها.
- الاستفادة من خدمة OpenCode Native الدائمة الموجودة بالفعل، وواجهات API الأصلية، ومخزنها وCache الأصليين، والـ permissions وSSE.
- استخدام Nginx الموجود لنقل محتوى الأسئلة والأجوبة مباشرة بعد فحص الصلاحية المناسب، دون Python body processing في المسار المستهدف.
- Python/Gateway للهوية والملكية والاشتراكات والتحكم الأمني الإداري فقط؛ لا إنشاء sidecar أو proxy أو queue أو مزود discovery service جديد.
- لا يعتبر تنفيذ التحقق عند حدود الطلبات تجاوزًا لهذه القاعدة؛ لكنه يجب أن يكون محدود الكلفة، مع استمرار الحماية حتى في حالات تبديل معرف الجلسة والتلاعب بالمسارات.
- تحسن تجربة العرض في Frontend مسموح دون محرك موازٍ، ولا يجوز أن يغيّر الحقيقة المحفوظة في Native.
- هذا القرار ينسخ أي اقتراح سابق بإنشاء authorization sidecar منفصل أو أي خدمة إضافية في هذه المذكرة؛ أي تغيير يمس multi-user isolation يظل مشروطًا باختبار أمني مسبق.
