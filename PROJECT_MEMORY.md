# ملخص المشروع — الحالة المعتمدة

الحالة المسموح بها للتعديل: فرع `updates` وسيرفر TEST فقط. LIVE و`master` خارج النطاق.

المعمارية الوحيدة: Python للتحقق الأمني والملكية وإدارة الحسابات وGitHub؛ Nginx يمرر الطلب المصرح به إلى OpenCode Native، ثم يعود JSON/SSE **من OpenCode عبر Nginx مباشرة إلى العميل**. لا Python AI proxy، ولا محرك منفصل لكل Workspace، ولا مزود/موديل مخزّن في قاعدة Gateway.

**مراجع التفاصيل الحالية**:
- [CANONICAL_NATIVE_FIRST_ARCHITECTURE_AR.md](docs/CANONICAL_NATIVE_FIRST_ARCHITECTURE_AR.md)
- [CANONICAL_GITHUB_AND_NATIVE_ATTACHMENTS_AR.md](docs/CANONICAL_GITHUB_AND_NATIVE_ATTACHMENTS_AR.md)
- [CANONICAL_TEST_SERVER_STATUS_AR.md](docs/CANONICAL_TEST_SERVER_STATUS_AR.md)

لا يستخدم هذا الملف لتخزين أوامر نشر أو ترحيلات أو سياسات تشغيل قديمة. لا تعدّ إصدارًا أو فحصًا قديمًا تعليمات نشطة، ولا تحذف بيانات العملاء أو تغير Live أثناء الإصلاح.
