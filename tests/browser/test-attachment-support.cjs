// Real capability helpers and support disclosure; jsdom, no vendor/model call.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const document=new JSDOM('<form><button id="attach"></button><select id="modelSelect"><option value="text">Text</option><option value="vision">Vision</option><option value="unknown">Unknown</option></select><div id="attachments"></div></form>').window.document;
const c={document,lang:'ar',attach:document.getElementById('attach'),attachmentList:document.getElementById('attachments'),
 attachmentModels:[{id:'text',capabilities:{input:{image:false,pdf:false}}},{id:'vision',capabilities:{input:{image:true,pdf:true}}},{id:'unknown'}],
 q:id=>document.getElementById(id),tr:(en,ar)=>c.lang==='ar'?ar:en,
 textElement:(tag,value='',cls='')=>Object.assign(document.createElement(tag),{textContent:value,className:cls})};
vm.createContext(c);const source=fs.readFileSync('dashboards.js','utf8');vm.runInContext(source.slice(source.indexOf('  const fileSupport='),source.indexOf('  const clearAttachments=')),c);
c.renderFileSupport();let support=document.querySelector('.composer-file-support');assert.ok(support);assert.equal(support.open,false);assert.match(support.textContent,/DOCX/);assert.match(support.textContent,/غير مهيأ/);
let result=c.attachmentSupport({name:'photo.png',type:'image/png'});assert.equal(result.blocked,true);assert.match(result.message,/قراءة الصور/);
result=c.attachmentSupport({name:'report.pdf',type:'application/pdf'});assert.equal(result.blocked,true);assert.match(result.message,/PDF/);
document.getElementById('modelSelect').value='vision';support.open=true;c.renderFileSupport();assert.equal(support.open,true);assert.match(support.textContent,/يدعمها/);assert.equal(c.attachmentSupport({name:'photo.jpg',type:'image/jpeg'}).blocked,false);
document.getElementById('modelSelect').value='unknown';c.renderFileSupport();assert.match(support.textContent,/غير مؤكد/);result=c.attachmentSupport({name:'photo.webp',type:'image/webp'});assert.equal(result.blocked,false);assert.match(result.message,/غير مؤكد/);
result=c.attachmentSupport({name:'تقرير.DOCX',mime:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'});assert.equal(result.blocked,false);assert.match(result.message,/يُستخرج نص DOCX/);assert.match(result.message,/لا تُقرأ الصور/);
result=c.attachmentSupport({name:'old.doc',mime:'application/msword'});assert.match(result.message,/أداة أو مهارة/);
c.lang='en';document.getElementById('modelSelect').value='text';c.renderFileSupport();assert.match(support.textContent,/not equipped to read/);assert.match(support.textContent,/16,000/);assert.match(support.textContent,/embedded images or macros/);assert.match(c.attach.title,/Supported attachments/);
assert.match(source,/renderFileSupport\(\);attachmentList.replaceChildren/);
console.log('8 PASSED / 0 FAILED / 0 SKIPPED: actual format disclosure, image/PDF rejection, vision selection, unknown support, DOCX text/embedded-image distinction, legacy tool-only formats, English/Arabic limits and refresh hook');
