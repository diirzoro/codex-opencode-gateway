"""Opt-in, isolated native OpenCode sessions; no model request or vendor key."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import pytest


@pytest.mark.skipif(not os.getenv('OPENCODE_TEST_BINARY'),reason='Set OPENCODE_TEST_BINARY to an existing supported binary')
def test_two_native_conversations_remain_available_without_closing():
    binary=os.environ['OPENCODE_TEST_BINARY']
    with tempfile.TemporaryDirectory(prefix='gateway-chat-test-') as directory:
        root=Path(directory);project=root/'project';project.mkdir()
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':str(root/'home'),'XDG_CONFIG_HOME':str(root/'config'),'XDG_DATA_HOME':str(root/'data'),'XDG_CACHE_HOME':str(root/'cache'),'OPENCODE_DISABLE_MODELS_FETCH':'true','OPENCODE_DISABLE_AUTOUPDATE':'true','OPENCODE_CONFIG_CONTENT':'{"permission":"ask"}'}
        base=f'http://127.0.0.1:{port}'
        def request(path,payload=None):
            data=None if payload is None else json.dumps(payload).encode()
            req=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
        with (root/'runtime.log').open('w') as log:
            process=subprocess.Popen([binary,'serve','--hostname','127.0.0.1','--port',str(port)],cwd=project,env=env,stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+20
                while True:
                    try:request('/global/health');break
                    except (OSError,urllib.error.URLError):
                        if process.poll() is not None or time.monotonic()>deadline:pytest.fail('Disposable OpenCode did not become ready; no model call attempted')
                        time.sleep(.2)
                first=request('/session',{'title':'First design'})
                second=request('/session',{'title':'Second design'})
                assert first['id']!=second['id']
                ids={row['id'] for row in request('/session')}
                assert {first['id'],second['id']}<=ids
                assert request('/session/'+first['id'])['title']=='First design'
                assert request('/session/'+second['id'])['title']=='Second design'
            finally:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
