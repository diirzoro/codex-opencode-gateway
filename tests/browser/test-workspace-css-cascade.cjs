// Uses already installed css-tree/jsdom via NODE_PATH; no browser or downloads.
const fs=require('node:fs'),assert=require('node:assert/strict');
const css=require('css-tree'),{JSDOM}=require('jsdom');
const html=fs.readFileSync('index.html','utf8'),dom=new JSDOM(html),doc=dom.window.document;
const workspace=doc.querySelector('#workspacePage .workspace-shell');workspace.classList.add('workspace-first','reference-workspace');
const sources=[fs.readFileSync('styles.css','utf8'),...Array.from(doc.querySelectorAll('style')).map(s=>s.textContent)];
function result(width,element,property){let winner;let order=0;
 for(const source of sources){const ast=css.parse(source,{parseCustomProperty:true});
  function walk(children,enabled=true){children.forEach(n=>{
   if(n.type==='Atrule'&&n.name==='media'&&n.block){const media=css.generate(n.prelude);const limits=[...media.matchAll(/(max|min)-width:\s*([\d.]+)px/g)];walk(n.block.children,enabled&&limits.every(m=>m[1]==='max'?width<=+m[2]:width>=+m[2]));}
   else if(n.type==='Rule'&&enabled){n.prelude.children.forEach(sel=>{const selector=css.generate(sel);let matches=false;try{matches=element.matches(selector)}catch{}if(!matches)return;
    let score=0;css.walk(sel,node=>{if(node.type==='IdSelector')score+=100;if(node.type==='ClassSelector'||node.type==='AttributeSelector'||node.type==='PseudoClassSelector')score+=10;if(node.type==='TypeSelector')score++;});
    n.block.children.forEach(d=>{if(d.type!=='Declaration'||d.property!==property)return;const candidate={important:!!d.important,score,order:order++,value:css.generate(d.value)};if(!winner||+candidate.important>+winner.important||candidate.important===winner.important&&(candidate.score>winner.score||candidate.score===winner.score&&candidate.order>winner.order))winner=candidate;});
   });}
  });}walk(ast.children);
 }return winner?.value;
}
for(const width of [390,700,900,1100,1366]){
 const columns=result(width,workspace,'grid-template-columns');
 assert.equal(columns,width<=1100?'minmax(0,1fr)':'var(--dashboard-rail-width) minmax(0,1fr) var(--panel-w,var(--dashboard-rail-width))');
}
workspace.classList.add('panel-docked');doc.getElementById('sessionSidebar').classList.add('open');
assert.equal(result(900,doc.getElementById('sessionSidebar'),'position'),'fixed');
console.log('6 passed: loaded CSS cascade at five viewport widths and docked project drawer (DOM/CSS parser, not rendered pixels)');
for(const dark of [false,true]){
 doc.documentElement.classList.toggle('dark',dark);
 assert.equal(result(1366,doc.documentElement,'--line'),'color-mix(in srgb,var(--text) 15%,var(--panel))');
 assert.equal(result(1366,doc.documentElement,'--surface-edge'),'color-mix(in srgb,var(--text) 15%,var(--panel))');
 assert.equal(result(1366,doc.documentElement,'--control-edge'),'color-mix(in srgb,var(--text) 18%,var(--panel))');
}
const carousel=doc.createElement('section');carousel.className='feature-carousel';const media=doc.createElement('div');media.className='home-media';carousel.append(media);doc.body.append(carousel);
assert.equal(result(1366,media,'border'),'1px solid var(--line)');
const method=doc.createElement('label');method.className='checkout-method';doc.body.append(method);
assert.equal(result(1366,method,'border'),'1px solid var(--line)');
assert.ok(html.includes(':focus-visible{outline:0;border-color:#2563eb'));
assert.ok(sources[0].includes('.checkout-method:has(input:checked){background:#e9f2ff;border:2px solid #3978c9;'));
console.log('5 passed: light/dark shared edges, Landing inner media, checkout resting border, preserved focus/selection (DOM/CSS parser/source)');

assert.equal(result(1366,doc.querySelector('.pricing'),'background'),'var(--panel2)');
console.log('1 passed: pricing section has a distinct theme-aware background');
assert.equal(result(900,doc.querySelector('.workspace-dashboard-rail')||(()=>{const e=doc.createElement('aside');e.className='workspace-dashboard-rail';workspace.prepend(e);return e;})(),'display'),'none');
console.log('1 passed: conversation rail defaults hidden at tablet/mobile widths');

for(const dir of ['ltr','rtl']){doc.documentElement.dir=dir;assert.equal(result(1366,workspace,'direction'),'inherit');assert.ok(result(1366,workspace,'grid-template-areas').includes('dashboard chat project'));}
console.log('2 passed: dashboard and tabbed project panel inherit LTR/RTL grid direction');
const outerFrame=doc.createElement('div');outerFrame.className='app-frame';const oldSidebar=doc.createElement('aside');oldSidebar.id='app-sidebar';oldSidebar.className='app-sidebar';outerFrame.append(oldSidebar);doc.body.append(outerFrame);const workspacePage=doc.getElementById('workspacePage');workspacePage.classList.add('active');
assert.equal(result(1366,oldSidebar,'display'),'none');assert.equal(result(1366,outerFrame,'grid-template-columns'),'minmax(0,1fr)');
workspacePage.classList.remove('active');assert.equal(result(1366,oldSidebar,'display'),'flex');assert.equal(result(1366,outerFrame,'grid-template-columns'),'248px minmax(0,1fr)');
console.log('2 passed: old shell sidebar/column removed only in Workspace and restored elsewhere');

const approvals=doc.createElement('div');approvals.className='chat-approvals';const card=doc.createElement('section');card.className='chat-approval';const allow=doc.createElement('button');allow.dataset.reply='once';card.append(allow);approvals.append(card);workspacePage.append(approvals);
assert.equal(result(1366,card,'border-radius'),'12px');assert.equal(result(1366,card,'border'),'1px solid var(--line)');assert.equal(result(1366,allow,'background'),'var(--soft)');
console.log('3 passed: actual approval card has rounded quiet frame and distinct allow-once action');

// Current approved pane width follows the Dashboard rail; the old 400px fixture
// failed against the unchanged baseline too. Keep that layout while testing edits.
const newConversation=doc.createElement('dialog');newConversation.className='new-conversation-dialog';doc.body.append(newConversation);
assert.equal(result(390,newConversation,'position'),'fixed');
assert.equal(result(390,newConversation,'width'),'min(360px,calc(100vw - 24px))');
assert.equal(result(390,doc.getElementById('promptInput'),'max-height'),'120px');
assert.equal(result(1366,doc.getElementById('promptInput'),'min-height'),'40px');
console.log('4 passed: compact nonmodal picker and bounded composer at mobile/desktop widths (CSS cascade, not pixels)');
