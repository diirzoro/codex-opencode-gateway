import { accessSync, constants, lstatSync, realpathSync, statSync,
  readFileSync, readlinkSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

// Read-only permission inventory. Use TWO disposable fixture directories.
// Never opens fixture contents, environment, command lines or credentials.
function inspectDirectory(input) {
  if (typeof input !== "string" || !path.isAbsolute(input))
    return { available:false, reason:"absolute_path_required" };
  try {
    if (lstatSync(input).isSymbolicLink() || realpathSync(input) !== input)
      return { available:false, reason:"noncanonical_path" };
    if (!statSync(input).isDirectory())
      return { available:false, reason:"directory_required" };
    const can=mode=>{try{accessSync(input,mode);return true;}catch{return false;}};
    return { available:true, readable:can(constants.R_OK),
      writable:can(constants.W_OK), traversable:can(constants.X_OK) };
  } catch(error) {
    return { available:false, reason:error.code === "ENOENT" ? "missing" : "unavailable" };
  }
}
function serviceIdentity(pid) {
  if (!/^[1-9][0-9]*$/.test(String(pid)))
    return { verified:false, reason:"service_pid_required" };
  try {
    // Strictly numeric PID and fixed metadata paths; never /proc/.../environ.
    const status=readFileSync(`/proc/${pid}/status`,"utf8");
    const selfStatus=readFileSync("/proc/self/status","utf8");
    const uid=status.match(/^Uid:\s+(\d+)\s+(\d+)/m);
    if(!uid)return {verified:false,reason:"service_identity_unavailable"};
    const sameEffectiveUid=Number(uid[2]) === process.geteuid();
    const fields=["Uid","Gid","Groups","CapEff","CapPrm","NoNewPrivs","Seccomp"];
    const field=(text,key)=>text.match(new RegExp("^"+key+":\\s*([^\\n]*)$","m"))?.[1].trim().replace(/\s+/g," ");
    const samePermissionContext=fields.every(key=>field(status,key) !== undefined &&
      field(status,key) === field(selfStatus,key));
    const sameSecurityLabel=readFileSync(`/proc/${pid}/attr/current`,"utf8") ===
      readFileSync("/proc/self/attr/current","utf8");
    const sameMountNamespace=readlinkSync(`/proc/${pid}/ns/mnt`) === readlinkSync("/proc/self/ns/mnt");
    const sameUserNamespace=readlinkSync(`/proc/${pid}/ns/user`) === readlinkSync("/proc/self/ns/user");
    const sameRoot=realpathSync(`/proc/${pid}/root`) === realpathSync("/proc/self/root");
    const verified=sameEffectiveUid && samePermissionContext && sameSecurityLabel &&
      sameMountNamespace && sameUserNamespace && sameRoot;
    return {verified,sameEffectiveUid,samePermissionContext,sameSecurityLabel,
      sameMountNamespace,sameUserNamespace,sameRoot,
      reason:verified ? "identity_and_filesystem_match" : "run_in_service_execution_context"};
  } catch{return {verified:false,reason:"service_identity_unavailable"};}
}
export function auditPermissions(own,other,pid) {
  const ownProject=inspectDirectory(own),otherTestProject=inspectDirectory(other);
  const distinct=typeof own === "string" && typeof other === "string" && path.resolve(own) !== path.resolve(other);
  const service=serviceIdentity(pid);
  const valid=distinct && ownProject.available && otherTestProject.available;
  const exposed=Boolean(valid && otherTestProject.traversable &&
    (otherTestProject.readable || otherTestProject.writable));
  const result=!valid || !service.verified ? "INCONCLUSIVE" :
    exposed ? "PERMISSION_EXPOSURE" : "NO_DIRECTORY_PERMISSION_EXPOSURE";
  return {audit:"Pi directory permissions; no fixture content access or mutation",
    result,service,distinct,ownProject,otherTestProject,
    crossProjectPermissionExposed:exposed,executionIsolationProven:false,
    limits:"Directory access is not proof of file readability or tool isolation. Test real Pi read/write/edit/bash with disposable canaries. Service context does not prove a future isolated worker context."};
}
if(process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href){
  const args=process.argv.slice(2);
  if(args.length !== 4 || args[2] !== "--pid"){
    console.error("Usage: node pi_readonly_isolation_audit.mjs /absolute/fixture-A /absolute/fixture-B --pid PI_SERVICE_PID");
    process.exitCode=2;
  }else{
    const r=auditPermissions(args[0],args[1],args[3]);
    process.stdout.write(JSON.stringify(r,null,2)+"\n");
    process.exitCode=r.result === "INCONCLUSIVE" ? 2 : r.result === "PERMISSION_EXPOSURE" ? 1 : 0;
  }
}
