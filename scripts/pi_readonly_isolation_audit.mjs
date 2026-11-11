import { accessSync, constants, realpathSync, statSync } from "node:fs";
import path from "node:path";
// Read-only audit. Run as the Pi TEST service account with TWO TEST fixtures.
const [own,other]=process.argv.slice(2);
if(!own||!other||!path.isAbsolute(own)||!path.isAbsolute(other)||path.resolve(own)===path.resolve(other)){
 console.error("Supply two distinct absolute TEST fixture paths.");process.exitCode=2;
}else{
 const can=(f,mode)=>{try{accessSync(f,mode);return true;}catch{return false;}};
 const check=f=>{try{const real=realpathSync(f),s=statSync(f);return {
  exists:true,readable:can(real,constants.R_OK),writable:can(real,constants.W_OK),
  traversable:s.isDirectory()?can(real,constants.X_OK):null,
  symlinkRedirect:path.resolve(f)!==real
 };}catch{return {exists:false}}};
 const ownProject=check(own),otherProject=check(other);
 const systemFile=check("/etc/hostname"),piExtensions=check(process.env.PI_CODING_AGENT_DIR||"/home/tahir/.pi/agent");
 process.stdout.write(JSON.stringify({
  audit:"Pi OS permissions (no file content access; no mutation)",
  uid:typeof process.getuid==="function"?process.getuid():null,
  ownProject,otherTestProject:otherProject,ordinarySystemFile:systemFile,piExtensions,
  crossProjectReadable:otherProject.readable===true,
  crossProjectWritable:otherProject.writable===true
 },null,2)+"\n");
 if(otherProject.readable||otherProject.writable)process.exitCode=1;
}
