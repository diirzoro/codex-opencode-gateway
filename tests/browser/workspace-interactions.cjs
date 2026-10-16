// Batch 1 only: no real provider requests, screenshots or signup journeys.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const root=path.resolve(__dirname,'../..');
const server=http.createServer((req,res)=>{
 const target=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname.replace(/\/$/,'/index.html'));
 if(!target.startsWith(root+path.sep)){res.writeHead(403).end();return;}
 try{res.setHeader('Content-Type',target.endsWith('.js')?'application/javascript':target.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(target));}catch{res.writeHead(404).end();}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--disable-features=Vulkan']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript({content:fs.readFileSync(path.join(__dirname,'fixture.js'),'utf8')+`
   const original=window.previewResponse;window.showQuestion=false;window.questionBody=null;
   window.previewMessages=Array.from({length:40},(_,i)=>({id:'m'+i,role:i%2?'assistant':'user',text:'Fixture message '+i+'\\n'+('Reading position test. '.repeat(35)),activity:[]}));
   window.previewResponse=url=>{const p=new URL(url,location.origin).pathname;if(p.endsWith('/questions'))return {data:{supported:true,requests:window.showQuestion?[{id:'q1',questions:[{question:'Choose colors',multiple:true,custom:true,options:[{label:'Blue',description:'Useful explanation',recommended:true},{label:'Green'}]}]}]:[]}};return original(url);};
   const fetchBefore=window.fetch;window.fetch=async(url,opts={})=>{if(String(url).endsWith('/questions/q1')){window.questionBody=JSON.parse(opts.body);window.showQuestion=false;return Response.json({accepted:true});}return fetchBefore(url,opts);};
  `});
  await page.goto('http://127.0.0.1:'+server.address().port);await page.evaluate(()=>window.openWorkspacePreview());
  await page.waitForFunction(()=>{const f=document.querySelector('#agentFeed');return f.scrollHeight-f.clientHeight-f.scrollTop<65;});
  await page.locator('#agentFeed').evaluate(f=>f.scrollTop=400);await page.waitForTimeout(100);
  const before=await page.locator('#agentFeed').evaluate(f=>f.scrollTop);
  await page.evaluate(async()=>{window.previewMessages.push({id:'new',role:'assistant',text:'New response '.repeat(100),activity:[]});await refreshMessages();});
  await page.waitForTimeout(100);const after=await page.locator('#agentFeed').evaluate(f=>f.scrollTop);
  assert(Math.abs(after-before)<3,'Reading position shifted');await page.locator('#workspaceJumpLatest').waitFor();
  await page.locator('#workspaceJumpLatest').click();await page.waitForFunction(()=>{const f=document.querySelector('#agentFeed');return f.scrollHeight-f.clientHeight-f.scrollTop<65;});
  await page.evaluate(async()=>{window.previewMessages.push({id:'new2',role:'assistant',text:'Streaming fixture '.repeat(50),activity:[]});await refreshMessages();});
  await page.waitForFunction(()=>{const f=document.querySelector('#agentFeed');return f.scrollHeight-f.clientHeight-f.scrollTop<65;});
  console.log('PASS scroll: preserve older reading position, Jump to Latest, follow new response');
  await page.evaluate(async()=>{window.showQuestion=true;await window.refreshWorkspaceQuestions();});
  await page.locator('.chat-questions input[value=Blue]').check();await page.locator('.chat-questions input[type=text]').fill('Custom answer');
  assert.equal(await page.locator('.question-recommended').count(),1);
  await page.locator('.chat-questions button[type=submit]').click();
  await page.waitForFunction(()=>window.questionBody!==null);assert.deepEqual(await page.evaluate(()=>window.questionBody.answers),[['Blue','Custom answer']]);
  console.log('PASS question: genuine recommendation, multiple choices plus custom answer');
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>{lang='ar';applyPrefs();});
  assert(await page.locator('#promptForm').evaluate(n=>n.getBoundingClientRect().right<=innerWidth+1));
  await page.evaluate(()=>{lang='en';applyPrefs();});assert.equal(await page.locator('html').getAttribute('dir'),'ltr');
  console.log('PASS responsive: Composer fits mobile; Arabic/English direction preserved');
  assert.deepEqual(errors,[]);await page.close();
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
