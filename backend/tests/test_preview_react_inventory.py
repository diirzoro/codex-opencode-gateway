"""Inventory reveals framework readiness without executing or printing commands."""
import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('react_inventory',Path(__file__).resolve().parents[2]/'scripts/preview-react-inspect.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_vite_react_readiness():
    data=module.summarize_manifest({'dependencies':{'react':'19','react-dom':'19'},
        'devDependencies':{'vite':'6'},'scripts':{'dev':'vite','build':'vite build'}})
    assert data['framework']=='vite'
    assert data['standard_scripts']==['build','dev']
    assert data['project_commands_executed'] is False

def test_commands_urls_and_private_names_are_not_exposed():
    data=module.summarize_manifest({'dependencies':{'react':'https://secret-token@example/private',
          '@private/internal-secret-package':'sensitive'},
          'scripts':{'build':'echo secret-password && curl private-url','private-secret-command':'secret'}})
    output=str(data)
    for secret in ['secret-token','secret-password','private-url','private-secret-command','internal-secret-package']:
        assert secret not in output

def test_malformed_optional_sections_do_not_execute_or_crash():
    data=module.summarize_manifest({'dependencies':['react'],'scripts':'run untrusted command'})
    assert data['framework']=='other' and data['standard_scripts']==[]

def test_non_object_manifest_rejected():
    with pytest.raises(ValueError): module.summarize_manifest(['react'])


def test_controlled_runtime_probe_is_valid_python_and_bounded_archive():
    import base64,io,tarfile
    path=Path(__file__).resolve().parents[2]/'scripts/preview-runtime-audit.py'
    probe_spec=importlib.util.spec_from_file_location('runtime_audit',path)
    probe=importlib.util.module_from_spec(probe_spec);probe_spec.loader.exec_module(probe)
    source=probe.probe_source('/var/lib/controlled-canary',"/var/lib/controlled-'other")
    compile(source,'main.py','exec')
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(probe.archive(source)))) as tar:
        assert tar.getnames()==['main.py']
        assert tar.extractfile('main.py').read()==source
        assert len(source)<4096
