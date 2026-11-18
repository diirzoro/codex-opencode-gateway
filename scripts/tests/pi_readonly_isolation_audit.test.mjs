import test from "node:test";
import assert from "node:assert/strict";
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,symlinkSync,rmSync,readdirSync} from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";
import {auditPermissions} from "../pi_readonly_isolation_audit.mjs";
function fixtures(t){
  const root=mkdtempSync(path.join(os.tmpdir(),"pi-permission-audit-"));
  t.after(()=>rmSync(root,{recursive:true,force:true}));
  const a=path.join(root,"a"),b=path.join(root,"b");mkdirSync(a);mkdirSync(b);
  return {root,a,b};
}
test("matching context detects cross-project directory exposure",t=>{
  const {a,b}=fixtures(t),r=auditPermissions(a,b,process.pid);
  assert.equal(r.service.verified,true);assert.equal(r.result,"PERMISSION_EXPOSURE");
  assert.equal(r.executionIsolationProven,false);
});
test("missing second fixture cannot pass",t=>{
  const {a,root}=fixtures(t),r=auditPermissions(a,path.join(root,"missing"),process.pid);
  assert.equal(r.result,"INCONCLUSIVE");assert.equal(r.otherTestProject.reason,"missing");
});
test("same fixture cannot masquerade as two accounts",t=>{
  const {a}=fixtures(t);assert.equal(auditPermissions(a,a,process.pid).result,"INCONCLUSIVE");
});
test("symlink and noncanonical paths are inconclusive",t=>{
  const {root,a,b}=fixtures(t),link=path.join(root,"link");symlinkSync(b,link);
  assert.equal(auditPermissions(a,link,process.pid).result,"INCONCLUSIVE");
  assert.equal(auditPermissions(a,b+"/",process.pid).result,"INCONCLUSIVE");
});
test("missing malformed or inaccessible service PID is inconclusive",t=>{
  const {a,b}=fixtures(t);
  for(const pid of [undefined,"../self","0","999999999999999"])
    assert.equal(auditPermissions(a,b,pid).result,"INCONCLUSIVE");
});
test("regular file and relative path rejected as directories",t=>{
  const {root,a}=fixtures(t),file=path.join(root,"file");writeFileSync(file,"fixture");
  assert.equal(auditPermissions(a,file,process.pid).result,"INCONCLUSIVE");
  assert.equal(auditPermissions("relative",a,process.pid).result,"INCONCLUSIVE");
});
test("inventory leaves canary intact and omits paths and contents",t=>{
  const {a,b}=fixtures(t),file=path.join(b,"canary"),marker="DISPOSABLE_MARKER_DO_NOT_REPORT";
  writeFileSync(file,marker);const before=readdirSync(b),output=JSON.stringify(auditPermissions(a,b,process.pid));
  assert.deepEqual(readdirSync(b),before);assert.equal(readFileSync(file,"utf8"),marker);
  assert.equal(output.includes(marker),false);assert.equal(output.includes(b),false);
});
test("CLI requires explicit context and reports exposure exit code",t=>{
  const {a,b}=fixtures(t),script=new URL("../pi_readonly_isolation_audit.mjs",import.meta.url).pathname;
  assert.equal(spawnSync(process.execPath,[script,a,b],{encoding:"utf8"}).status,2);
  // Run the CLI against its own PID: an exec child may have a different
  // capability/seccomp context from the test runner, which must not pass.
  const code=`process.argv=[process.execPath,${JSON.stringify(script)},${JSON.stringify(a)},${JSON.stringify(b)},"--pid",String(process.pid)];await import(${JSON.stringify(script)});`;
  const r=spawnSync(process.execPath,["--input-type=module","-e",code],{encoding:"utf8"});
  assert.equal(r.status,1);assert.equal(JSON.parse(r.stdout).result,"PERMISSION_EXPOSURE");
});
