const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('dashboards.js','utf8');
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.events={};this.hidden=false;this.textContent='';}
 append(...nodes){for(const n of nodes){if(n.parentElement)n.parentElement.children=n.parentElement.children.filter(x=>x!==n);n.parentElement=this;this.children.push(n);}}
 prepend(n){this.append(n);this.children.unshift(this.children.pop());}
 addEventListener(k,fn){this.events[k]=fn;}
 setAttribute(k,v){this[k]=v;}
 replaceChildren(...nodes){this.children=[];this.append(...nodes);}
 querySelector(selector){return this.children.find(n=>selector==='#'+n.id)||this.children.map(n=>n.querySelector(selector)).find(Boolean);}
}
const textElement=(tag,text='',cls='')=>Object.assign(new Element(tag),{textContent:text,className:cls});
const btn=(id,en,ar,action,cls='')=>Object.assign(textElement('button',en,cls),{id,onclick:action});
const c={textElement,btn,text:(tag,en)=>textElement(tag,en),tr:en=>en,document:{createElement:tag=>new Element(tag)},activeProject:{source_type:'blank'},activeWorkspace:{id:'local'},projectRoot:new Element('details'),storageChip:new Element('span'),filesRefresh:Object.assign(new Element('button'),{onclick:()=>42}),updateProjectIdentity(){},window:{openGithubProject:()=>{c.opened=true;},workspaceRetentionNotice:()=>''}};
vm.createContext(c);
vm.runInContext(source.slice(source.indexOf("  const projectGroups="),source.indexOf('  function projectFileFolder('))+source.slice(source.indexOf('  function placeCurrentProject('),source.indexOf('  async function loadProjectGroups('))+';this.buckets=projectBuckets;',c);
c.placeCurrentProject();assert.equal(c.buckets.size,2);assert.equal(c.buckets.get('local').meta.children[0],c.storageChip);assert.equal(c.buckets.get('local').summary.children.at(-1),c.filesRefresh);assert.equal(c.storageChip.hidden,true);
c.storageData={used_mb:2,remaining_bytes:3*1048576};vm.runInContext(source.slice(source.indexOf('  renderStorage=()=>'),source.indexOf('  async function loadStorage(')),c);c.renderStorage();assert.equal(c.storageChip.hidden,false);assert.match(c.storageChip.textContent,/2 MB.*3.0 MB/);
c.activeProject={source_type:'github'};c.activeWorkspace={id:'github'};c.placeCurrentProject();assert.equal(c.storageChip.hidden,true);assert.equal(c.storageChip.textContent,'');assert.equal(c.buckets.get('local').meta.children.length,0);assert.equal(c.buckets.get('github').meta.children[0],c.storageChip);assert.equal(c.filesRefresh.onclick(),42);assert.ok(!c.buckets.get('local').summary.children.includes(c.filesRefresh));
const link=c.buckets.get('github').summary.children.find(n=>n.id==='linkWorkspaceGithubProject');let prevented=0;link.events.click({preventDefault(){prevented++;},stopPropagation(){prevented++;}});link.onclick();assert.equal(prevented,2);assert.equal(c.opened,true);
const list=new Element('div'),opened=[];
Object.assign(c,{activeSession:{id:'one'},sessionsCount:new Element('small'),sessionRows:[],sessionFilter:'all',search:{value:''},q:()=>list,selectSession:row=>opened.push(row.id),sessionAction:()=>{},updateSend:()=>{}});
vm.runInContext(source.slice(source.indexOf('  function renderRuntimeSessions('),source.indexOf('  refreshSessions=async function')),c);
c.renderRuntimeSessions([{id:'one',title:'Current conversation',lifecycle:'active'},{id:'two',title:'Another conversation',lifecycle:'closed'}]);assert.equal(list.children.length,2);assert.equal(list.children[0].children[0]['aria-current'],'true');assert.equal(list.children[0].children[0].className,'conversation-name');list.children[1].children[0].onclick();assert.deepEqual(opened,['two']);assert.equal(list.children[1].children[0].textContent,'Another conversation');
{
 const names=['pane','modes','projectGroups','sessionsSection','previewPanel','sessionsBody','newSessionButton','sessionsSummary','sessionTabs','search','conversationsMode','shell','projectbar'];
 const fixture={projectPanelBrand:new Element('div'),textElement,btn,text:(tag,en)=>textElement(tag,en),tr:en=>en,document:{createElement:tag=>new Element(tag)},window:{openConnections(){}},placeCurrentProject(){}};
 for(const n of names)fixture[n]=new Element('div');
 const list=Object.assign(new Element('div'),{id:'sessionList'});fixture.sessionsBody.append(list);fixture.sessionsSection.append(fixture.sessionsBody);
 vm.createContext(fixture);vm.runInContext(source.slice(source.indexOf('  placeCurrentProject();pane.replaceChildren('),source.indexOf('  pane.append(paneResizer);')),fixture);
 const rail=fixture.shell.children[0];assert.equal(rail.id,'workspaceConversationRail');assert.ok(rail.children.includes(fixture.sessionsSection));assert.equal(fixture.sessionsSection.hidden,false);assert.ok(!fixture.pane.children.includes(fixture.sessionsSection));assert.equal(fixture.conversationsMode.hidden,false);assert.equal(fixture.sessionsBody.querySelector('#sessionList'),list);assert.ok(fixture.sessionsSummary.children.includes(fixture.newSessionButton));assert.ok(fixture.pane.children.includes(fixture.projectGroups));assert.ok(fixture.pane.children.includes(fixture.previewPanel));
}
console.log('5 passed: storage/refresh ownership, real storage values, GitHub action, text conversation navigation, single native-list reference layout (VM, not browser)');
