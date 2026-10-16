const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const app=fs.readFileSync('app.js','utf8'),enhancements=fs.readFileSync('enhancements.js','utf8');
(async()=>{
 for(const scenario of ['fresh','expired','social','authenticated','admin']){
  const actions=[],c={authReady:Promise.resolve(),interfaceReady:Promise.resolve(),window:{authRestoreExpired:scenario==='expired'},currentUser:scenario==='authenticated'?{id:'owner',role:'customer'}:scenario==='admin'?{id:'admin',role:'admin'}:null,location:{hash:scenario==='social'?'#social=error':''},page:async p=>actions.push(p),openWorkspaceAfterLogin:async()=>actions.push('restore-owned-workspace'),document:{documentElement:{classList:{remove(){}}}},toast(){}};
  vm.createContext(c);vm.runInContext(app.slice(app.indexOf('const navigationReady='),app.indexOf('// GitHub authorization/repository metadata'))+';this.done=navigationReady;',c);await c.done;
  assert.deepEqual(actions,scenario==='authenticated'?['restore-owned-workspace']:scenario==='admin'?['adminPage']:scenario==='social'?['authPage']:['landing']);
 }
 const c={copy:{en:{},ar:{}}};for(const language of ['en','ar'])for(let i=1;i<=4;i++){c.copy[language]['b'+i+'t']=language+'title'+i;c.copy[language]['b'+i+'d']=language+'body'+i;}
 vm.createContext(c);vm.runInContext(enhancements.slice(enhancements.indexOf('    function homeWithPlatformBenefits('),enhancements.indexOf('    async function renderHomeCarousel()')),c);
 const admin={id:3,title_en:'Admin announcement',title_ar:'إعلان',body_en:'News',body_ar:'خبر',cta_url:'/account',image_url:'/image'};
 const rows=c.homeWithPlatformBenefits([admin]);assert.equal(rows.length,5);assert.equal(rows[4],admin);assert.equal(rows[0].title_ar,'artitle1');assert.equal(rows[3].body_en,'enbody4');
 assert.equal(c.homeWithPlatformBenefits(rows).length,5);assert.equal(c.homeWithPlatformBenefits(null).length,4);
 const nodes={homeCarousel:{replaceChildren(){}}},state={};Object.assign(c,{document:{getElementById:id=>nodes[id]},home:state,api:async()=>{throw Error('offline');},homeBuildShell(){state.built=true;state.track={};},homeRenderCards(){},homeUpdate(){},homeSchedule(){}});
 vm.runInContext(enhancements.slice(enhancements.indexOf('    async function renderHomeCarousel()'),enhancements.indexOf('    window.renderHomeCarousel =')),c);await c.renderHomeCarousel();assert.equal(state.items.length,4);state.remoteItems=[admin];await c.renderHomeCarousel();assert.equal(state.items.at(-1),admin);
 const html=fs.readFileSync('index.html','utf8');assert.ok(!html.includes('--line:#2563eb'));assert.ok(!html.includes('--line:#60a5fa'));assert.ok(!html.includes(':root *{border-color:var(--line)}'));assert.match(html,/--control-edge:color-mix/);assert.match(html,/:focus-visible\{outline:0;border-color:#2563eb/);
  console.log('10 passed: 5 entry routes, 4 benefit/admin/dedup/fallback cases, quiet tokens with focus preserved (VM/source, not real browser)');
})().catch(error=>{console.error(error);process.exitCode=1;});
