# المرجع المعماري الوحيد — OpenCode Native First
**توضيح المالك النهائي: 29 أكتوبر 2026 | TEST وupdates فقط | هذا قرار معماري؛ لا يثبت صحة النشر أو علاج الأعطال التشغيلية**

## 1. قاعدة المالك النهائية: التحقق بكل طلب، والرد المباشر دون رجوع إلى Python
**التوضيح الصريح للمالك:** لا مانع من مرور **كل طلب محادثة** على Python للتحقق الأمني من هوية العميل وصلاحياته وملكية Workspace/Session. المشكلة القديمة المرفوضة هي أن **رد OpenCode نفسه** كان يعود إلى Python ليعيد Python تمريره إلى العميل. هذا النمط ممنوع؛ الرد وSSE يجب أن ينتقلا من Native إلى Nginx ثم إلى المتصفح مباشرة.

**المسار الملزم للطلبات المحمية:**
```text
Client → Nginx → Python/FastAPI (auth + ownership + policy decision only)
                            └─ X-Accel-Redirect → Nginx internal → OpenCode Native
OpenCode Native → Nginx → Client (response body / stream / SSE; NEVER via Python)
```
- **Python/FastAPI/PostgreSQL:** تسجيل الدخول، حسابات العملاء، العضوية، الاشتراكات، الصلاحيات والملكية، ملفات المشاريع وحمايتها، تكامل GitHub والتفويضات والتدقيق. يجوز التحقق الأمني **عند كل طلب** إلى OpenCode؛ لكن لا تنفيذ AI، ولا استلام stream للرد، ولا JSON response proxy لمحتوى المحادثات، ولا بناء مسار ثانٍ لتنفيذ أدوات/نماذج.
- **OpenCode Native:** جهة الحقيقة الوحيدة لتنفيذ وتخزين الجلسات والمحادثات والرسائل والنماذج والمزودين والوكلاء والأدوات وTodo والأسئلة والموافقات والإيقاف وSSE. يُستعمل Native API الأصلي الموجود دائمًا، بلا محرك موازٍ أو per-workspace engine أو OpenCode Web.
- **Nginx:** بعد قرار السماح الصادر من Python، يحوّل الطلب داخليًا إلى Native عبر `X-Accel-Redirect` ويعيد **جسم الاستجابة والتدفق مباشرة للعميل**؛ لا ينقل المحتوى عائدًا إلى Python. يحمي بيانات اعتماد Native الداخلية ولا يفتح raw Native للإنترنت.
- **OS/filesystem:** العزل الفعلي بين العملاء ضروري، ولا يكفي `directory` وحده لضمان العزل داخل Native مشترك.

**لا تُفسّر كلمة «اتجاه واحد» باعتبارها إزالة فحص Python عند الطلبات التالية؛** معناها بالتحديد أن **مسار رد النموذج لا يعود إلى Python** بعد التفويض، بينما يمكن التحقق من كل طلب وارد لحماية العملاء.

## 2. ما ثبت من المصدر وما يجب تحسينه دون إعادة بناء
- في `backend/app/routes/native_sessions.py` تستقبل الدالة `transport()` طلب العميل، وتقرأ POST للتحقق من محتواه وحدوده، وتنفذ `authorize_native()`، ثم تعيد رأس `X-Accel-Redirect` مع `X-Native-URI` إلى Nginx. **هذا لا يجعل Python هو معالج رد النموذج؛** لكنه يبقي وقت التفويض جزءًا من زمن وصول الطلب إلى Native.
- في `docs/NATIVE_SESSION_TEST_NGINX.conf` يُظهر مثال التكوين `location @native_session_test` مع `proxy_pass` إلى upstream داخلي و`proxy_buffering off`، و`@native_discovery_test` منفصلًا. **الملف مرجع تكوين مقترح وليس إثباتًا بحد ذاته أن Nginx الحي مطبّق حرفيًا**؛ إثبات الإعداد الجاري والقياس على TEST مطلوب.
- في `native-session-client.js` ترسل الواجهة `/native-session/{workspace}/session/{id}/prompt_async`؛ الاستقبال النهائي والتوليد من Native، والـSSE عبر Nginx بعد السماح.
- **الخلل المؤكد بنيويًا ليس رجوع الرد إلى Python**؛ لا دليل عليه في هذا المسار الحالي من المصدر. نقاط التأخير أو الرفض قبل التسليم هي تكرار ملكية/metadata Native، وفحص quota الذي قد يمسح ملفات المشروع، و`context()` الذي قد يعيد409. لا تدّع أن أي نقطة منها هي سبب العطل الفعلي دون response detail أو قياس.
- ارفع الأداء بقياس ثم إزالة الفحوص المكررة غير الضرورية، لا بإلغاء التحقق الأمني أو استعمال token مفتوح أو تغيير طريقة رد Native إلى Python.
- إصلاحات `uncertain` و`prompt_async` و`Recover` في المصدر ليست دليلًا على نجاح النسخة المنشورة؛ اختبر SHA على TEST دون إعادة إرسال تلقائي للطلبات الغامضة.

## 3. العوائق والحالة
- المصدر الحالي يحافظ على مسار التفويض عبر Python **في كل طلب**، ثم الرد/stream من Native عبر Nginx مباشرة للعميل، وهو مطلب المالك النهائي. العيوب المتبقية في التأخير والرفض ومصالحة الرسائل والملفات تُفحص منفصلة.
- المذكرة V3.9 القديمة القسم13.1 حذّرت من metadata المتكرر و`usage_bytes()` ومسح `rglob('*')` في المسار الحرج. مطلوب قياس الأثر، وليس نسب كل البطء إليه.
- سجلات VPS 29 أكتوبر 08:02 UTC: كثير من `GET /api/native-test/workspaces/.../sessions` أعاد409، مع `prompt_async` واحد أعاد200. الأسباب الممكنة في `context()`: مشروع مؤرشف، جذر Workspace مفقود، إعدادات Native تحتاج مراجعة. **لم تُستخلص response bodies الحاسمة**. لا تعمم أن كل Native فشل، ولا تمس الملفات بحذف أو نقل.
- إصلاح مصدر `e1fa147bfe77` يخص false uncertain receipts وstale history؛ كان غير منشور وقت التوثيق. تأكيد SHA المنفذ على VPS مستقل عن GitHub HEAD.
- حدود shared Native credential store ومزودين متعددين وحماية tool execution لم يثبت قبولها الشامل. لا تتجاوزها بافتراض عزل directory.

## 4. قبول معماري ملزم
اختبارات old/new conversation، متعددة المستخدمين، Native prompt/provider/model/tools/file/SSE، سحب صلاحية لحظي، ملكية user→project→workspace→session، ملفات ومفاتيح منفصلة، معدلات latency وmetadata calls قبل/بعد. لا تغيير LIVE/master أو ports أو خدمة Native أو shared config. لا إعلان PASS من اختبار موك أو HTTP200 وحده.

## 5. حدود المستندات
هذا **المرجع الوحيد لقرارات المعمارية**. مذكرات فحص VPS لا تعيد تعريفها. المذكرة التاريخية `OPENCODE_GATEWAY_MASTER_SINGLE_MEMO_V3_9_2026-10-27_AR.md` تحفظ الأدلة القديمة، لكن لا تلغي توضيح المالك الأخير: Python يفحص الطلبات المرسلة للحماية، ولا يستقبل جسم رد OpenCode أو SSE لإعادة تمريره.
