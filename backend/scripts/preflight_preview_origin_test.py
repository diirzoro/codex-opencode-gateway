#!/usr/bin/env python3
"""Read-only TEST origin inventory. Never prints env secrets or nginx -T output."""
import ipaddress
import json
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import time
from urllib.parse import urlsplit

TEST = 'test.opencode-gateway.codes'
PREVIEW = 'preview-test.opencode-gateway.codes'


def run(argv, timeout=10):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


def nginx_tree(text):
    # Preserve quoted braces; ignore comments. No variable expansion/execution.
    tokens = re.findall(r'''\#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[{};]|[^\s{};"']+''', text)
    tokens = [t for t in tokens if not t.startswith('#')]
    position = 0
    def parse(nested=False):
        nonlocal position
        result=[];words=[]
        while position<len(tokens):
            token=tokens[position];position+=1
            if token=='}':
                if not nested or words:raise ValueError('invalid nginx structure')
                return result
            if token in ('{',';'):
                if not words:raise ValueError('invalid nginx directive')
                result.append((words[0],words[1:],parse(True) if token=='{' else []));words=[]
            else:words.append(token.strip('"').strip("'"))
        if nested or words:raise ValueError('incomplete nginx structure')
        return result
    return parse()


def walk(nodes):
    for name,args,children in nodes:
        yield name,args,children
        yield from walk(children)


def selected_servers(text):
    result=[]
    for name,args,children in walk(nginx_tree(text)):
        if name!='server':continue
        names=[value for key,values,_ in children if key=='server_name' for value in values]
        selected=sorted(set(names)&{TEST,PREVIEW})
        if not selected:continue
        upstreams=[];certs=[];keys=[]
        for key,values,_ in walk(children):
            if key=='proxy_pass' and values:
                url=urlsplit(values[0])
                if url.scheme=='http' and url.hostname in {'127.0.0.1','localhost','::1'} and not url.username and not url.password:
                    upstreams.append('http://'+('['+url.hostname+']' if ':' in url.hostname else url.hostname)+':'+str(url.port or 80))
            if key in {'ssl_certificate','ssl_certificate_key'} and values:
                value=values[0]
                if value.startswith('/') and not re.search(r'[$\r\n\x00]',value):
                    (certs if key=='ssl_certificate' else keys).append(value)
        result.append({'server_names':selected,'loopback_upstreams':sorted(set(upstreams)),
            'certificate_files':sorted(set(certs)),'key_paths':sorted(set(keys))})
    return result


def dns(host):
    result=run(['getent','ahosts',host],timeout=6)
    found=set()
    for line in result.stdout.splitlines():
        try:found.add(str(ipaddress.ip_address(line.split()[0])))
        except (ValueError,IndexError):pass
    return sorted(found)


def certificate_covers(path,host):
    try:
        data=ssl._ssl._test_decode_cert(path)
        if not data.get('notAfter') or ssl.cert_time_to_seconds(data['notAfter'])<=time.time():return False
        for kind,name in data.get('subjectAltName',()):
            name=name.lower()
            if kind=='DNS' and (host==name or name.startswith('*.') and host.endswith(name[1:]) and host.count('.')==name.count('.')):
                return True
    except (OSError,ValueError,ssl.SSLError):pass
    return False


def database_metadata(raw):
    # Do not output username/password/query parameters or arbitrary URL text.
    parsed=urlsplit(raw)
    host=parsed.hostname or ''
    name=parsed.path.lstrip('/')
    return {'configured':bool(raw),
        'host':host if re.fullmatch(r'[A-Za-z0-9_.:-]+',host) else 'hidden',
        'port':parsed.port or 5432,
        'database':name if re.fullmatch(r'[A-Za-z0-9_-]+',name) else 'hidden',
        'test_named':bool(re.search('test',name,re.IGNORECASE))}


def main():
    try:
        pid_text=run(['systemctl','show','opencode-gateway-test.service','-p','MainPID','--value']).stdout.strip()
        if not pid_text.isdigit() or int(pid_text)<=1:
            print('BLOCKED: TEST Gateway is not running');return 1
        root=Path('/proc')/pid_text
        env={}
        for item in (root/'environ').read_bytes().split(b'\0'):
            key,separator,value=item.partition(b'=')
            if separator:env[key.decode(errors='replace')]=value.decode(errors='replace')
        print(json.dumps({'test_gateway_pid':int(pid_text),'working_directory':str((root/'cwd').resolve()),
            'credential_encryption_key_present':bool(env.get('CREDENTIALS_ENCRYPTION_KEY')),
            'preview_origin_already_set':bool(env.get('PREVIEW_PUBLIC_ORIGIN')),
            'pg_dump_available':shutil.which('pg_dump') is not None,
            'certbot_available':shutil.which('certbot') is not None}))
        print(json.dumps({'test_database':database_metadata(env.get('DATABASE_URL',''))}))
        nginx=run(['/usr/sbin/nginx','-T'])
        print(json.dumps({'nginx_configuration_valid':nginx.returncode==0}))
        if nginx.returncode==0:
            if len(nginx.stdout)>2_000_000:raise ValueError('nginx configuration too large')
            for server in selected_servers(nginx.stdout):
                print(json.dumps({'test_nginx_server':server}))
                for cert in server['certificate_files']:
                    print(json.dumps({'public_certificate':cert,'covers_preview_hostname':certificate_covers(cert,PREVIEW)}))
        for host in (TEST,PREVIEW):print(json.dumps({'hostname':host,'dns_addresses':dns(host)}))
        print('READ_ONLY: No configuration, service, DNS, certificate, database or customer file was changed. Key paths are metadata only; private keys were not read.')
        return 0
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        print('BLOCKED: TEST origin inventory unavailable ('+type(error).__name__+'). No changes made.')
        return 1


if __name__=='__main__':raise SystemExit(main())
