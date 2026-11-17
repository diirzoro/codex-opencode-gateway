"""Fixed offline React/Vite build driver and bounded artifact validation."""
import io
import tarfile
from pathlib import Path
from .preview_worker_archive import extract_into_sandbox, UnsafePreviewArchive

MAX_ARTIFACT = 20 * 1024 * 1024
BUILD_SECONDS = 120

# The only executable driver is installed with the worker code. Project scripts
# and Vite configuration execute only inside the network-none sandbox.
BUILD_SCRIPT = r'''
const fs=require('fs'),cp=require('child_process'),path=require('path');
const root='/build/project',cache='/build/npm-cache';
fs.mkdirSync('/build/home',{recursive:true});fs.mkdirSync('/build/tmp',{recursive:true});
fs.writeFileSync('/build/user.npmrc','');fs.writeFileSync('/build/global.npmrc','');
fs.cpSync('/workspace',root,{recursive:true,dereference:false});
fs.rmSync(path.join(root,'dist'),{recursive:true,force:true});
const env={PATH:process.env.PATH,HOME:'/build/home',TMPDIR:'/build/tmp',
 NODE_OPTIONS:'--max-old-space-size=256',NODE_ENV:'development',
 npm_config_userconfig:'/build/user.npmrc',npm_config_globalconfig:'/build/global.npmrc',
 npm_config_registry:'https://registry.npmjs.org',npm_config_cache:cache};
const flags=['--offline','--ignore-scripts','--no-audit','--no-fund'];
function run(args){const r=cp.spawnSync('npm',args,{cwd:root,env,encoding:'utf8',
 timeout:90000,maxBuffer:100000});if(r.status!==0){process.stderr.write((r.stderr||r.stdout||'Build command failed').slice(-8000));process.exit(1)}}
const packages=fs.readdirSync('/preview-packages').sort();
if(packages.some(file=>!/^\d{4}\.tgz$/.test(file)))process.exit(2);
if(packages.length)run(['cache','add',...packages.map(file=>'/preview-packages/'+file),...flags]);
run(['ci','--include=dev',...flags]);
const manifest=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
if(typeof manifest.scripts?.build!=='string'){
 process.stderr.write('A build script that produces dist/index.html is required');process.exit(2);
}
run(['run','build',...flags]);
const entry=path.join(root,'dist/index.html');
if(!fs.existsSync(entry)||!fs.statSync(entry).isFile()||fs.lstatSync(entry).isSymbolicLink())process.exit(3);
fs.writeFileSync('/build/complete','ready');
setInterval(()=>{},1000);
'''.replace('\n',' ')

def extract_artifact(raw,destination):
    """Accept Docker cp tar directories, but only extract validated regular files."""
    if len(raw)>MAX_ARTIFACT+1024*1024:raise UnsafePreviewArchive('Build artifact exceeds quota')
    normalized=io.BytesIO();total=0;entries=0
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as source,tarfile.open(fileobj=normalized,mode='w') as output:
        for item in source:
            entries+=1
            if entries>20000:raise UnsafePreviewArchive('Too many build artifact entries')
            name=item.name[2:] if item.name.startswith('./') else item.name
            if item.isdir():
                if name in {'','.','dist'}:continue
                # Validate even directory-only traversal entries before ignoring them.
                if name.startswith('/') or '\\' in name or any(p in {'','.','..'} for p in name.rstrip('/').split('/')):
                    raise UnsafePreviewArchive('Unsafe artifact directory')
                continue
            if not item.isfile() or item.issym() or item.islnk():raise UnsafePreviewArchive('Build links are not supported')
            total+=item.size
            if total>MAX_ARTIFACT:raise UnsafePreviewArchive('Build artifact exceeds quota')
            member=tarfile.TarInfo(name);member.size=item.size
            with source.extractfile(item) as stream:output.addfile(member,stream)
    destination=Path(destination);destination.mkdir(mode=0o755)
    normalized.seek(0)
    with tarfile.open(fileobj=normalized,mode='r:') as archive:extract_into_sandbox(archive,destination)
    if not (destination/'index.html').is_file():raise UnsafePreviewArchive('Build did not produce dist/index.html')
    for file in destination.rglob('*'):file.chmod(0o755 if file.is_dir() else 0o644)
