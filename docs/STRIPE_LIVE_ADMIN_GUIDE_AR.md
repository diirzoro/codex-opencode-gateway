# Stripe LIVE وPayPal — دليل إعداد الإدارة (13 نوفمبر 2026)

> هذه الميزة محفوظة على فرع `updates` ولا تُفعّل تلقائياً عند نشر الكود. تشغيل دفع حقيقي يحتاج مفاتيح حساب تاجر LIVE وWebhook مُسجّلاً في Stripe، ثم موافقة صريحة من لوحة الإدارة. لا ترسل الأسرار في ChatGPT أو GitHub Issues.

## أهداف التنفيذ

- **Stripe LIVE**: الدفع بالبطاقة عبر Stripe-hosted Checkout في البيئة الحقيقية فقط، دون استقبال أو حفظ بيانات البطاقة على Gateway.
- **Stripe TEST**: اختبار تشخيصي منفصل لا يُفعّل أي اشتراك حقيقي؛ تبقى وظائفه القديمة.
- **PayPal**: إخفاء من خيارات العملاء عبر قرار الإدارة، وليس إزالة تكامله أو سجلاته. يمكن إعادة إظهاره من الإدارة بعد التحقق من حساب تاجر LIVE وإضافة/تأكيد إعداداته الديناميكية.
- لا تعديل في `pi-central.service` أو جلسات Pi أو قاعدة بيانات TEST؛ استخدام جداول LIVE الموجودة دون ترحيل مخطط جديد.
- اشتراك Gateway المدفوع يُفعّل **فقط** بعد التحقق من دفع حقيقي عبر API خادم Stripe أو Webhook موقّع. هذا **دفع مرة واحدة للفترة المحددة في الخطة، وليس اشتراك Stripe متجدد تلقائياً**.

## الخطوات في لوحة الإدارة

1. افتح **Admin Dashboard → Billing → Flexible payment & bank connections**.
2. اختر/أنشئ ملف `stripe` من القالب الموجود مع `connection_mode=api` و`environment=live`.
3. أدخل مفاتيحك التي يولدها حساب التاجر في Stripe: `pk_live_...` (Publishable key)، `sk_live_...` (Secret key)، و`whsec_...` (Webhook signing secret). الحقول السرية تُشفّر في قاعدة البيانات ولا تظهر كاملة بعد حفظها. المفاتيح التجريبية `pk_test_`/`sk_test_` لا تصلح هنا.
4. في **Stripe Dashboard** سجّل Webhook HTTPS التالي، واضبط الأحداث `checkout.session.completed` و`checkout.session.async_payment_succeeded`:

   `https://opencode-gateway.codes/api/billing/webhooks/stripe`

   ثم انسخ سر توقيع **نقطة LIVE نفسها** إلى حقل `webhook_secret` في لوحة إدارة Gateway. إعداد Webhook داخل حساب Stripe الخارجي ضروري؛ لا يمكن توليده من واجهة Gateway دون إذن حساب التاجر.
5. من قسم **Stripe LIVE & PayPal visibility** في نفس صفحة الإدارة، اضغط **Enable Stripe LIVE · hide PayPal**، ثم أكد صراحةً أنه تحصيل أموال حقيقية. السيرفر يتحقق من وجود المفاتيح `sk_live_/pk_live_/whsec_`، ومن حساب Stripe وقدرته على تحصيل أموال حقيقية، ومن وجود Webhook فعّال بالعنوان الصحيح والأحداث المطلوبة.
6. بعد النشر والتحقق، ادخل بحساب عميل تجريبي مشروع حقيقي، وافحص أن اختيار Stripe يظهر وPayPal مخفي. **لا تُجرِ أي دفعة مالية حقيقية إلا بعد نجاح الاختبارات والمراجعة التشغيلية.**

## تفعيل/إخفاء PayPal من الإدارة

- الملف الديناميكي `paypal` يقبل `merchant_id` و`client_id` و`client_secret`، مع البيئة `live`؛ يُقرأ من تخزين الإدارة المشفّر، مع بقاء إعدادات بيئة PayPal القديمة كبديل للتركيبات الموجودة.
- **Show PayPal to customers** يتحقق من وصول OAuth لحساب PayPal LIVE، وينشئ وسيلة PayPal عامة باستخدام بنية `BillingMethod` الموجودة إذا لم تكن مهيأة. لا ينشئ اشتراكات ولا عمليات خصم بمجرد إظهار الوسيلة.
- **Hide PayPal from customers** يخفي PayPal من `/api/billing/available-methods` ومن واجهة العميل، ويرفض إنشاء طلبات PayPal الجديدة حتى عبر استدعاء API مباشر. لا يحذف الطلبات السابقة أو يمنع تسويتها.
- لا يُسمح بعرض حساب PayPal Sandbox للعملاء على منصة LIVE عند إعادة التفعيل.
- ملاحظة: تغيير إعدادات حساب التاجر أو بيئته أثناء وجود طلبات قديمة معلّقة قد يتطلب تسوية يدوية منظمة مع المزوّد؛ لا تحذف الطلبات أو تبدّل البيئة بقصد إصلاح سجل قديم.

## التدفق الآمن لمدفوعات Stripe

- الواجهة تستدعي `POST /api/billing/stripe/checkout` مع معرّف خطة، والخادم ينشئ `PaymentOrder` بحالة انتظار الدفع ثم يتصل بـStripe (Idempotency-Key لكل طلب) وينشئ جلسة Checkout مستضافة.
- المتصفح يُحوّل إلى رابط `checkout.stripe.com` موثوق. العودة إلى `/?stripe_live=return` **ليست دليل دفع**. بعد العودة يستعلم الخادم عن الجلسة مباشرة من Stripe.
- الـWebhook `POST /api/billing/webhooks/stripe` لا يستخدم Cookies؛ يتحقق من التوقيع على **Raw Body** مع زمن سماح 5 دقائق. يتحقق قبل التفعيل من `livemode` و`payment_status` و`amount_total` والعملة ومعرّفات الطلب/الخطة/المستخدم ومُعرّف PaymentIntent. لا يقبل رسائل TEST أو بيانات عميل غير موقعة.
- يعتمد على `PaymentOrder` الموجود ويقفل سجل العملية أثناء المصالحة. الأحداث المكررة لا تكرر مدة الاشتراك. إذا انقطعت Gateway قبل حفظ معرّف جلسة Stripe، يمكن استعادة الربط باستخدام `metadata.order_id` المصادَق عليه.
- لا تزال أحداث الاسترداد/الاعتراضات وإجراءات النزاعات المالية والمراقبة التشغيلية تحتاج خطة مراجعة قبل إطلاق الإنتاج للعامة. لا تتعامل مع نجاح اختبار وحدة على أنه اعتماد دفع مالي كامل.

## الاختبارات وعدم النشر قبل التحقق

- Workflow بلا وصول إلى VPS أو مفاتيح دفع: `.github/workflows/stripe-live-safe-check.yml`. يفحص `compileall` و`node --check` و`pytest` على `backend/tests/test_stripe_live_checkout.py`.
- يجب التأكد من نجاح CI، وإنشاء Webhook حقيقي وتجربة توقيعه، وتجربة كاملة لمبلغ حقيقي متفق عليه ومراجعة تفعيل الاشتراك **مرة واحدة فقط** ثم التحقق من استمرارها بعد إعادة الدخول. لا تُدخل مفاتيح أو بيانات بطاقة حقيقية في سجلات الاختبار.
- أبقِ LIVE على إصدار GitHub الحالي حتى اعتماد الشيفرة؛ لا تعِد تشغيل خدمة Pi Central المشتركة. إذا لزم إيقاف تحصيل Stripe بعد النشر: **Disable new Stripe checkouts** من Admin، مع إبقاء استقبال Webhooks وتسوية الطلبات المسبقة.

## ملفات التنفيذ

- `backend/app/services/stripe_live_checkout.py` — اتصال Stripe وفحص الجلسة والتوقيع وتفعيل الطلب.
- `backend/app/routes/billing.py` — إنشاء Checkout وقراءة حالته وWebhook.
- `backend/app/routes/payment_gateways.py` — ضبط التفعيل/الإخفاء بواسطة Admin.
- `backend/app/services/payment_gateway_config.py` — تخزين أعلام الدفع مشفّرة وربط التفعيل ببصمة مفاتيح LIVE.
- `backend/app/services/paypal.py` — الاعتماد على بيانات Merchant من Admin مع fallback للإعدادات السابقة.
- `backend/app/routes/management.py` — إخفاء PayPal من بيانات وسائل دفع العميل.
- `enhancements.js` و`dashboards.js` و`index.html` — واجهات الإدارة والدفع والعودة.
