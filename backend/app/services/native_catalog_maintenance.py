"""Administrative scheduling of OpenCode's own `models --refresh` command.

No catalog, model enumeration, native DB/cache writes, AI execution or daemon.
The existing Gateway maintenance loop invokes sweep; Native owns the cache.
CLI completion does NOT prove that the running server reloaded its snapshot.
"""
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time

from fastapi import HTTPException
from ..config import settings

UNIT=os.getenv('OPENCODE_NATIVE_SERVICE','opencode-native-test.service')
NOTICE='Native CLI refresh updates its own cache. Immediate in-process catalog reload is not exposed by this API; no restart/dispose is performed.'


def test_scope():
    from ..routes.native_sessions import deployment
    if deployment() not in {'test','live'}:
        raise HTTPException(503,'Native catalog maintenance requires a verified deployment')

def maintenance_leader():
    """One Gateway may refresh a shared Native model cache at a time."""
    from ..routes.native_sessions import deployment
    flag=os.getenv('OPENCODE_NATIVE_MAINTENANCE_ENABLED')
    if flag is None:return deployment()=='test'
    return flag.lower() in {'1','true','yes'}

def require_maintenance_leader():
    test_scope()
    if not maintenance_leader():
        raise HTTPException(503,'Model refresh is delegated to the other Gateway')


def state_path():
    root=settings.runtime_root
    if root.is_symlink():raise HTTPException(503,'Unsafe maintenance state path')
    root.mkdir(parents=True,exist_ok=True)
    return root/'native-catalog-maintenance.json'


def load():
    path=state_path()
    if path.is_symlink():raise HTTPException(503,'Unsafe maintenance state file')
    try:
        metadata=path.stat()
        if metadata.st_uid!=os.geteuid() or stat.S_IMODE(metadata.st_mode)!=0o600 or metadata.st_size>16384:raise ValueError()
        value=json.loads(path.read_text())
        if not isinstance(value,dict):raise ValueError()
        if value.get('interval_days') not in {7,14}:raise ValueError()
        return {key:item for key,item in value.items() if key in {'interval_days','next_attempt_at','last_attempt_at','last_finished_at','outcome','native_pid_unchanged'}}
    except FileNotFoundError:return {'interval_days':7,'next_attempt_at':None,'last_attempt_at':None,'outcome':'not_attempted'}
    except (ValueError,OSError):raise HTTPException(503,'Catalog maintenance state requires operator reconciliation') from None


def save(value):
    path=state_path();descriptor,name=tempfile.mkstemp(prefix='.native-catalog-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w') as handle:
            json.dump(value,handle);handle.flush();os.fsync(handle.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def acquire():
    path=state_path().with_suffix('.lock')
    descriptor=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    metadata=os.fstat(descriptor)
    if metadata.st_uid!=os.geteuid() or stat.S_IMODE(metadata.st_mode)!=0o600 or metadata.st_nlink!=1:
        os.close(descriptor);raise HTTPException(503,'Unsafe catalog maintenance lock')
    try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(descriptor);raise HTTPException(409,'Native catalog refresh is already in progress') from None
    return descriptor


def service_context():
    # Read the ACTUAL unit/PID before selecting its executable or HOME/XDG. No
    # guessed /home/ path, new installation, copied auth file, or printed env.
    try:
        result=subprocess.run(['systemctl','show',UNIT,'--no-pager','-p','MainPID','-p','ActiveState','-p','UnitFileState','-p','Restart'],capture_output=True,timeout=5,check=True)
        fields=dict(line.split('=',1) for line in result.stdout.decode().splitlines() if '=' in line)
        pid=int(fields.get('MainPID','0'))
        if fields.get('ActiveState')!='active' or pid<=0:raise ValueError()
        process=Path('/proc')/str(pid)
        arguments=process.joinpath('cmdline').read_bytes().split(b'\0')
        if b'web' in arguments or b'serve' not in arguments:raise ValueError()
        executable=process.joinpath('exe').resolve(strict=True)
        if executable.name not in {'opencode','opencode.exe'} or not executable.is_file():raise ValueError()
        original=dict(item.split(b'=',1) for item in process.joinpath('environ').read_bytes().split(b'\0') if b'=' in item)
        environment={key.decode():value.decode() for key,value in original.items() if key in {b'HOME',b'XDG_CONFIG_HOME',b'XDG_DATA_HOME',b'XDG_CACHE_HOME',b'OPENCODE_MODELS_URL',b'OPENCODE_MODELS_PATH'}}
        if not environment.get('HOME'):raise ValueError()
        for key in ('HOME','XDG_DATA_HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME'):
            if key not in environment:continue
            directory=Path(environment[key])
            if not directory.is_absolute():raise ValueError()
            if directory.exists():
                actual=directory.stat();inside=(process/'root'/str(directory).lstrip('/')).stat()
                if (actual.st_dev,actual.st_ino)!=(inside.st_dev,inside.st_ino):raise ValueError()
        environment.update(PATH=os.defpath,OPENCODE_DISABLE_MODELS_FETCH='true',OPENCODE_DISABLE_AUTOUPDATE='true',OPENCODE_DISABLE_PROJECT_CONFIG='true')
        # Recheck PID start identity; a recycled PID cannot select another context.
        identity=process.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]
        return {'pid':pid,'identity':identity,'binary':str(executable),'environment':environment,'autostart':fields.get('UnitFileState','unknown'),'recovery':fields.get('Restart','unknown')}
    except (OSError,ValueError,UnicodeError,subprocess.SubprocessError):
        raise HTTPException(503,'Existing headless Native service context is unavailable; inspect ExecStart/HOME/XDG with the TEST operator') from None


def public(value,context=None):
    return {**value,'notice':NOTICE,'in_process_reload_verified':False,
            'native_service':UNIT,'service_pid':context['pid'] if context else None,
            'autostart':context['autostart'] if context else 'unverified','recovery':context['recovery'] if context else 'unverified'}


def status():
    test_scope();value=load()
    try:context=service_context()
    except HTTPException:return {**public(value),'available':False}
    return {**public(value,context),'available':True}


def configure(days):
    require_maintenance_leader()
    if days not in {7,14}:raise HTTPException(422,'Choose 7 or 14 days')
    descriptor=acquire()
    try:
        value=load();value.update(interval_days=days,next_attempt_at=time.time()+days*86400);save(value)
        return public(value)
    finally:os.close(descriptor)


def refresh():
    require_maintenance_leader();descriptor=acquire()
    try:
        value=load();context=service_context();started=time.time()
        value.update(last_attempt_at=started,next_attempt_at=started+value['interval_days']*86400,outcome='running');save(value)
        try:
            # The supported CLI performs its own atomic last-good-cache update.
            # No server process is launched and no cache file is opened here.
            result=subprocess.run([context['binary'],'models','--refresh','--pure','--print-logs','--log-level','WARN'],env=context['environment'],cwd=context['environment']['HOME'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=45)
            failed=result.returncode!=0 or b'failed to fetch models.dev' in result.stderr.lower()
            value['outcome']='failed' if failed else 'cli_completed_reload_unverified'
        except (OSError,subprocess.SubprocessError):value['outcome']='failed'
        # Do not claim an unchanged PID without actually checking it afterward.
        try:
            current=service_context();value['native_pid_unchanged']=current['pid']==context['pid'] and current['identity']==context['identity']
        except HTTPException:value['native_pid_unchanged']=False
        value['last_finished_at']=time.time();save(value)
        return public(value,context)
    finally:os.close(descriptor)


def sweep():
    test_scope()
    if not maintenance_leader():return
    value=load()
    if value['next_attempt_at'] is None:
        # Initial boot schedules maintenance, never a download on first login.
        configure(value['interval_days']);return
    if value['next_attempt_at']<=time.time():refresh()
