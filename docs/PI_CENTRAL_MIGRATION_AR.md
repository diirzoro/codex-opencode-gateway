# مذكرة مشروع Pi Central — مستقلة عن مذكرات OpenCode
**تاريخ التوثيق:** 2026-11-09  
**المستودع:** `diirzoro/codex-opencode-gateway`  
**فرع التطوير الوحيد:** `updates` — لا تعديل على `master` أو LIVE  
**حالة الربط:** كود المحوّل موجود في GitHub؛ لم يُنشر أو يُختبر على VPS بعد.

## 1. الهدف والقرارات الثابتة
- الاستغناء تدريجيًا عن OpenCode **في TEST فقط أولًا** واستبداله بـPi Coding Agent.
- تشغيل محرك Pi **مركزي واحد** يخدم لاحقًا TEST وLIVE، مع فصل ملكية المشاريع والجلسات والملفات وعدم مزج قواعد البيانات. لا تفعيل LIVE في هذه المرحلة.
- Nginx مفتاح التوجيه؛ إبقاء الدومينات ومسارات الواجهة والمنافذ العامة كما هي. `8000` للـLIVE Gateway، `8001` للـTEST Gateway.
- الاحتفاظ بقاعدة TEST المنفصلة، حسابات المستخدمين، صلاحياتهم، إدارة المشاريع، GitHub، الفوترة، وعناصر Dashboard.
- **الأولوية السرعة ثم الأمان**: Pi الأصلي يدير المحادثات والأدوات؛ Node.js فقط HTTP/SSE ↔ RPC. Python يبقى لخدمات إدارة المنصة الحالية ولا يدخل في تنفيذ الذكاء.
- لا إنشاء `releases` أو نسخ Backups إضافية أثناء الربط. الإبقاء على إصدار TEST الحالي. لا حذف أو إيقاف خدمة OpenCode المشتركة حتى اكتمال التحويل.
- نموذج العمل: مشروع واحد = جلسة Pi واحدة دائمة، لا توليد جلسة جديدة في كل Refresh.
- عدم إعلان اتصال المزود «Verified» بمجرد ظهور النماذج أو نجاح حفظ المفتاح؛ يلزم نجاح رد AI فعلي لتأكيد الاعتماد.

## 2. البنية القديمة المؤكدة من سجلات VPS
```text
test.opencode-gateway.codes
  Nginx
    /                        -> TEST Gateway 127.0.0.1:8001
    /native-direct/api/*     -> OpenCode Native proxy 127.0.0.1:18098
    /native-direct/api/provider,agent -> 127.0.0.1:18097
    /native-probe/*          -> OpenCode Native
    /native-session/*        -> Gateway routes (as configured)

opencode-gateway.service           inactive, port 8000, LIVE DB
opencode-gateway-test.service      active, port 8001, TEST DB
opencode-native-test.service       active, shared OpenCode, 127.0.0.2:4097
```
**إعدادات الخدمة قد تتغير بمرور الوقت؛ هذا يصف الخرج المرسل بتاريخ المذكرة، لا قراءة جديدة من السيرفر.**

- الواجهة النشطة: `app.js`، `native-session-client.js`، `assets/native-direct/app.js`، `assets/native-direct/index.html`.
- الملفات في `releases/release-*/dashboards.js` كانت نسخ نشر متكررة. حذف المستخدم 13 إصدارًا قديمًا، وأبقى إصدار TEST الفعلي:
  `release-02bb6190915dc52fa9e4220bf9bc14d78764fc61-9648eb52`.
- حُسم عدم استخدام `directory` القادم من المتصفح بوصفه إذن ملكية: Gateway هو مصدر بيانات الملكية عبر `/api/auth/me` و`/api/workspaces` و`/api/workspaces/{id}`.

## 3. خطوات Pi المنفذة بالفعل على VPS
### 3.1. إزالة Cline
حذف `/home/tahir/cline-test`؛ لا تثبيت Global ولا عملية Cline. تمت إزالة تقرير التدقيق المؤقت. Cline 0.2.0 أظهر 25 تحذيرًا أمنيًا، منها اثنان حرجان من اعتماديات `simple-git`.

### 3.2. تثبيت Pi
```text
Node.js: 22.23.3
npm: 10.9.9
Package: @earendil-works/pi-coding-agent@1.5.0
Install path: /home/tahir/pi-test
Installed packages: 123
npm audit: 0 findings at test time
pi --version: 1.5.0
pi --version peak RSS: 96464 KB (~94 MiB), elapsed 0.75 s
```
هذه قياسات أمر الإصدار فقط وليست قياس تنفيذ مهام Agent.

### 3.3. Pi RPC
`{"type":"get_state"}` أعاد `success=true` ومعرّف جلسة. في تشغيل أولي: `get_available_models` أعاد 0 نماذج، ثم `pi --list-models openrouter` عرض كتالوجًا واسعًا يتضمن Kimi وOpenAI وGoogle وDeepSeek. **هذا يثبت عرض الكتالوج، لا نجاح طلب مدفوع أو صلاحية اعتماد**.

### 3.4. الخدمة المركزية الدائمة
أنشأ المستخدم `/home/tahir/pi-test/pi-central.mjs` و`pi-central.service`.
```text
systemctl is-enabled pi-central.service => enabled
systemctl is-active pi-central.service => active
curl --unix-socket /run/pi-central/pi.sock http://localhost/health
=> {"service":"pi-central","status":"ready"}
```
خدمة VPS الحالية تملك `/health` فقط وتبدأ Pi مع `--no-session --no-tools`؛ ليست محوّل محادثات بعد. عمليات Node وPi لا يلزم أن تظهر بالشكل نفسه في قائمة `ps`.

## 4. البنية الجديدة المطلوبة
```text
Browser: TEST Dashboard
       |
     Nginx  (نفس الدومين والمسارات العامة، وبدون منفذ إنترنت جديد)
       |
       +-- /api/* -> TEST Gateway :8001 (مصادقة، ملكية، GitHub، DB)
       |
       +-- /native-direct/api/* -> Pi Central Node.js HTTP bridge, UNIX socket
                                        |
                                    Pi RPC workers
                                        |
                           Per-project persistent session
                                        |
                             OpenRouter / other providers
```
خدمة Pi واحدة، لكنها تدير جلسات مميزة لكل مشروع. لا تُحوَّل صلاحيات جلسة إلى مشروع آخر. LIVE يظل بدون تعديل إلى ما بعد قبول TEST.

## 5. العمل البرمجي الذي أُضيف لفرع updates
**ملف:** `integration/pi-central.mjs`  
**Commit:** `e74d87cf55d0ce825f8a5f4be8e27101adc8e8c2`.

وُضع **محوّل أولي غير منشور** يستخدم مكتبات Node.js الأساسية وعمليات Pi RPC دون إضافة اعتماديات خارجية. يتضمن:
- HTTP على UNIX socket، مع منع فتح منفذ عام.
- طلب تحقق من جلسة Gateway قبل تنفيذ العمليات والتحقق من ملكية المجلد عن طريق بيانات Workspace الحقيقية، بدل قبول `directory` وحده.
- عملية Pi منفصلة لكل مشروع نشط بحد أقصى عمليتين، مع حفظ الجلسة عبر `--session-id` و`--session-dir`.
- نقاط توافق أولية: `/session`، `/session/status`، `/session/{id}`، `/session/{id}/message`، `/session/{id}/prompt_async`، `/session/{id}/abort`، `/event`، `/health`.
- SSE بسيط، وحدود حجم للـJSON، وحدود مهلة، وإغلاق عمال Pi الخاملين.
- **`--no-tools` مؤقتًا** لأن صلاحيات ملفات نظام التشغيل ومخاطر Shell لم تُعزل بعد.
- ترجمة جزئية لأحداث Pi والرسائل نحو شكل متوافق مع واجهة OpenCode، وليست جميع وظائف الواجهة بعد.

**الحدود التقنية الصريحة:**
- كتالوج المزودين، وإضافة/حذف المفاتيح، والأذونات، Todo، Questions، الملفات، أدوات Edit/Bash، ورسائل SSE التفصيلية ما زالت غير مكتملة. لذلك **ممنوع تغيير Nginx العام إلى هذا المحوّل قبل إكمال واجهات الواجهة المطلوبة**.
- لا توجد اختبارات تشغيل حقيقية للمحوّل الجديد على VPS. لا يُعد `GET /health` وحده دليلًا على جاهزية المحادثة.
- تشغيل عدة عمليات Pi تحت مستخدم OS واحد ليس عزل ملفات قويًا. قبل أدوات Shell يلزم عزل OS/حاويات أو حسابات منفصلة وقيود موارد وملفات.
- لا تعتمد أية جهة على استجابات HTTP 204/200 بوصفها إثباتًا لإتمام استجابة AI. Pi ينتج أحداثًا لاحقة يجب متابعتها حتى نهاية التشغيل.
- الأداء الأولي يحتاج تحسين الاستعلامات إلى Gateway عند زيادة عدد المستخدمين، دون التخلي عن التحقق من الملكية.

## 6. طريقة التفعيل لاحقًا دون تعقيد نشر
1. إكمال واجهات التوافق اللازمة للـDashboard داخل الملف المركزي نفسه، بدل بناء Dashboard أو Agent جديدين.
2. نقل محتوى `integration/pi-central.mjs` إلى مكان تشغيل `pi-central.service` الحالي بعد المراجعة، وتشغيله بالخدمة الموجودة بدل إنشاء خدمة ثانية. لا تكرار مجلدات `releases`.
3. منح Nginx حق استخدام UNIX socket بشكل محدد؛ الصلاحية الحالية `0600` مع `RuntimeDirectoryMode=0700` لا تسمح بالاتصال من Nginx تلقائيًا.
4. تغيير **TEST فقط** لتوجيه `/native-direct/api/*` إلى Pi، مع ضمان أن المسار الذي يستقبله Node.js مطابق لما ينتجه Rewrite/Proxy في Nginx.
5. الحفاظ على `/ -> 127.0.0.1:8001` كما هو، وعدم تغيير LIVE أو وحدات OpenCode المشتركة.
6. إجراء قبول تكامل واحد حقيقي للجلسة والرسائل وSSE وربط الملكية، ثم تمكين الأدوات بعد عزل نظام التشغيل.
7. عند اعتماد TEST، يمكن ربط LIVE بالخدمة المركزية نفسها **مع مجال فصل بيئات وأذونات مستقل**. لا تُستخدم جلسة TEST لخدمة LIVE.

## 7. سجل الحالة النهائي عند كتابة المذكرة
| البند | الحالة |
|---|---|
| إزالة Cline | تم على VPS |
| تثبيت Pi وتدقيق npm | تم |
| RPC الأصلي | تم |
| عرض كتالوج OpenRouter | تم |
| systemd Pi Central وتشغيل /health | تم |
| حذف 13 نسخة TEST قديمة | تم وفق خرج المستخدم |
| إنشاء كود محوّل Pi في updates | تم على GitHub |
| نشر المحوّل على VPS | **لم يتم** |
| تبديل Nginx TEST إلى Pi | **لم يتم** |
| إرسال Prompt فعلي عبر Dashboard إلى Pi | **لم يتم** |
| حماية Shell والملفات متعددة المستخدمين | **لم تتم** |
| تعديل LIVE | لم يتم — محظور الآن |

## 8. توجيه عملي للوكيل التالي
استمر من هذه المذكرة **بدون تكرار اختبارات التثبيت السابقة**. راجع ملف `integration/pi-central.mjs` أولًا ثم أكمل بروتوكولات Dashboard اللازمة في فرع `updates`. لا تُدّعِ أن Pi مربوط بالويب طالما أن Nginx لا يوجهه ولم يكتمل توافق API. لا تلمس LIVE ولا تعيد إطلاق مسار نشر يولد `releases`. احفظ أي تقدم جديد داخل **هذه المذكرة المستقلة فقط**.

## 9. المصادر المرجعية
- `docs/OPENCODE_GATEWAY_CURRENT_AGREEMENT_AR.md` — اتفاق معماري سابق يصف حدود OpenCode؛ تتقدم عليه قرارات Pi الواردة هنا في ما يخص المحرك البديل.
- `backend/app/routes/workspaces.py` — ملكية Workspaces وربط Project Session.
- `native-session-client.js` و`app.js` — عقد الواجهة القديمة مع OpenCode.
- Pi official documentation: https://pi.dev/docs/latest/rpc و https://pi.dev/docs/latest/cli .

## 10. قرار التنظيف المعماري — 2026-11-09
- المستخدم رفض تراكم محولات متعددة وملفات نشر وفحص مؤقتة.
- حُذف من فرع `updates` الملفان المضافان حديثًا `integration/pi-benchmark.mjs` و`integration/install-pi-bridge-test.sh` نهائيًا؛ لا يُعاد إنشاؤهما.
- احتُفظ فقط بملف ربط Pi قيد التطوير `integration/pi-central.mjs` وهذه المذكرة المستقلة. الكود الحالي غير مكتمل التوافق مع الواجهة ولم يُنشر إلى VPS.
- الهدف هو الاستبدال داخل البنية الحالية، وليس تشغيل OpenCode وPi معًا على TEST بشكل دائم. قبل حذف ملفات OpenCode العاملة، يجب تحويل الإشارات والمسارات والنقاط المستخدمة فعليًا إلى Pi لكي لا يتوقف TEST. لا حذف في LIVE.
- نُفّذت عملية التنظيف في GitHub على فرع `updates` فقط؛ لا يتغير VPS تلقائيًا مع الحذف من المستودع.
