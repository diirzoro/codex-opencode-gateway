// DOM safety and source-preserving formatting; no HTML parser or remote resources.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Node{
 constructor(tag,text=''){this.tagName=tag;this.children=[];this._text=text;this.classList={add(){}};}
 set textContent(v){this._text=v;this.children=[];}
 get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this._text='';this.children=nodes;}
 all(tag){return this.children.flatMap(n=>[...(n.tagName===tag?[n]:[]),...n.all(tag)]);}
}
const source=fs.readFileSync('app.js','utf8'),copies=[];
const c={document:{createElement:tag=>new Node(tag),createTextNode:text=>new Node('#text',text)},textElement:(tag,text='',cls='')=>Object.assign(new Node(tag,text),{className:cls}),feedAction:(kind,text)=>{copies.push(text);return new Node('button');}};
vm.createContext(c);vm.runInContext(source.slice(source.indexOf('function renderAgentText('),source.indexOf('async function refreshMessages()')),c);
function render(text){const host=new Node('div');c.renderAgentText(host,text);return host;}
{
 const host=render('## Hello\n\nA **bold** and `code` line.\n\n- First\n- Second\n\n1. One\n2. Two');
 assert.equal(host.all('h3')[0].textContent,'Hello');assert.equal(host.all('strong')[0].textContent,'bold');assert.equal(host.all('code')[0].textContent,'code');assert.equal(host.all('ul')[0].all('li').length,2);assert.equal(host.all('ol')[0].all('li').length,2);
}
{
 const code='<script>alert(1)</script>\nconst key = "<img src=x onerror=alert(1)>";';const host=render('```js\n'+code+'\n```');
 assert.equal(host.all('pre')[0].all('code')[0].textContent,code);assert.equal(copies.at(-1),code);assert.equal(host.all('script').length,0);assert.equal(host.all('img').length,0);
}
{
 const input='<img src=https://tracker.invalid onerror=alert(1)>\n<script>run()</script>\n[jump](javascript:alert(1))';const host=render(input);
 assert.equal(host.textContent,input);for(const tag of ['script','img','a','iframe'])assert.equal(host.all(tag).length,0);
}
{const host=render('```python\nprint("streaming")');assert.equal(host.all('code')[0].textContent,'print("streaming")');}
{const host=render('~~~'+('x'.repeat(100))+'\nhello\n~~~');assert.equal(host.all('span')[0].textContent.length,40);assert.equal(host.all('code')[0].textContent,'hello');}
{const host=render('**unfinished\n\n`unfinished');assert.match(host.textContent,/\*\*unfinished/);assert.match(host.textContent,/`unfinished/);}
console.log('6 passed: formatting, code copy fidelity, HTML/URL inertness, streaming fence and bounded labels (VM, not browser)');
