// Execute actual UI builders; no TEST deployment or rendered-pixel claim.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('dashboards.js','utf8');
const {window}=new JSDOM('<main></main>'),{document}=window;
const texts=[],c={window,document,Map,lang:'ar',texts,activeProject:{id:'project-id',name:'مشروعي',repository:'owner/repo',branch:'work'},activeWorkspace:{id:'private-workspace-id'},previewIdentity:document.createElement('div'),previewProjectSelect:document.createElement('select'),previewStatus:{},tr:(en,ar)=>c.lang==='ar'?ar:en,textElement:(tag,value='',cls='')=>Object.assign(document.createElement(tag),{textContent:value,className:cls})};
vm.createContext(c);
vm.runInContext(source.slice(source.indexOf('  function text('),source.indexOf('  function title(')),c);
vm.runInContext(source.slice(source.indexOf('  function updatePreviewIdentity('),source.indexOf('  const previewPath=')),c);
c.updatePreviewIdentity();
assert.equal(c.previewIdentity.querySelector('strong').textContent,'مشروعي');
assert(!c.previewIdentity.textContent.includes('private-workspace-id'));
c.activeProject.branch=null;c.updatePreviewIdentity();assert(c.previewIdentity.querySelector('small').hidden);
vm.runInContext(source.slice(source.indexOf('  const projectGroups='),source.indexOf('  function projectFileFolder('))+'\nglobalThis.groups=projectBuckets;globalThis.button=linkGithub;',c);
document.querySelector('main').append(c.groups.get('github').group);
for(const language of ['ar','en','ar']){
 c.lang=language;
 // Same translation refresh used by applyPrefs.
 for(const [node,en,ar] of texts){if(!node.firstChild)node.textContent=c.tr(en,ar);else if(node.firstChild.nodeType===3)node.firstChild.textContent=c.tr(en,ar);}
 assert(c.button.querySelector('svg'),'translation must preserve the icon');
 assert.equal(c.button.textContent,'','no long translated label in an icon-size button');
}
const group=c.groups.get('github').group,summary=group.querySelector('summary');
assert(group.open);summary.click();assert(!group.open);summary.click();assert(group.open);
let opened=0;window.openGithubProject=()=>{opened++;};c.button.click();assert.equal(opened,1);assert(group.open,'import action must not toggle the section');
const optionCode=source.match(/option\.value=workspace\.id;\s*option\.textContent=[^;]+;/)[0];
for(const name of ['مشروع عربي','English project','<script>text only</script>']){
 const ctx={document,option:document.createElement('option'),project:{name,repository:'owner/repo'},workspace:{id:'hidden-id'},tr:en=>en};vm.runInNewContext(optionCode,ctx);
 assert.equal(ctx.option.textContent,name);assert.equal(ctx.option.value,'hidden-id');assert.equal(ctx.option.children.length,0);
}
console.log('PASS: name-only labels, internal workspace selection, escaped names, bilingual icon stability, collapse/expand and independent import action');
