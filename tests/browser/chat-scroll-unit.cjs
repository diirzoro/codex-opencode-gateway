// Fake geometry only; native browser layout/streaming is a separate open gate.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('app.js','utf8');
const code=source.slice(source.indexOf('function workspaceLatestControl'),source.indexOf('async function refreshMessages'));
let button,scroll;const feed={scrollTop:800,scrollHeight:1000,clientHeight:200,parentElement:{append(n){button=n;}},addEventListener(name,fn){scroll=fn;},scrollTo(opts){this.scrollTop=opts.top-this.clientHeight;scroll();}};
const context={lang:'en',document:{getElementById:()=>button,createElement:()=>({dataset:{},setAttribute(){}})}};
vm.createContext(context);vm.runInContext(code,context);context.workspaceLatestControl(feed);
assert.equal(button.hidden,true);console.log('PASS latest-control: hidden at tail');
feed.scrollTop=300;scroll();assert.equal(button.hidden,false);console.log('PASS latest-control: visible while reading history');
button.onclick();assert.equal(button.hidden,true);assert.equal(feed.scrollTop,800);console.log('PASS latest-control: returns to newest messages');
