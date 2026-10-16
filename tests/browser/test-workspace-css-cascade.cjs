// Uses already installed css-tree/jsdom via NODE_PATH; no browser or downloads.
const fs=require('node:fs'),assert=require('node:assert/strict');
const css=require('css-tree'),{JSDOM}=require('jsdom');
const html=fs.readFileSync('index.html','utf8'),dom=new JSDOM(html),doc=dom.window.document;
const workspace=doc.querySelector('#workspacePage .workspace-shell');workspace.classList.add('reference-workspace');
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
 assert.equal(columns,width<=700?'minmax(0,1fr)':width<=1100?'var(--conversation-rail-width) minmax(0,1fr)':'var(--conversation-rail-width) minmax(0,1fr) var(--panel-w,400px)');
}
workspace.classList.add('panel-docked');doc.getElementById('sessionSidebar').classList.add('open');
assert.equal(result(900,doc.getElementById('sessionSidebar'),'position'),'fixed');
console.log('6 passed: loaded CSS cascade at five viewport widths and docked project drawer (DOM/CSS parser, not rendered pixels)');
