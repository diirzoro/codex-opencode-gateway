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
