"""Regression tests: never persist provider API keys without real authentication.

Mocks never transmit real secrets, make live network requests, or touch accounts.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from app.routes import management


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, headers):
        self.calls.append((url, headers))
        return self.response


def patch_http(monkeypatch, response):
    client = FakeClient(response)

    def make_client(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        return client

    monkeypatch.setattr(management._ai_httpx, "Client", make_client)
    return client


def test_unknown_provider_fails_closed_without_any_outbound_probe(monkeypatch):
    def never_client(**kwargs):
        raise AssertionError("Unknown providers must not trigger network requests")
    monkeypatch.setattr(management._ai_httpx, "Client", never_client)
    with pytest.raises(HTTPException) as exc:
        management._ai_verify("unconfigured-pi-provider", "dummy-key-for-test")
    assert exc.value.status_code == 422


def test_authenticated_opencode_zen_console_models(monkeypatch):
    response = SimpleNamespace(status_code=200, json=lambda: {
        "opencode": {"id": "opencode", "models": {"example": {"id": "example"}}}})
    client = patch_http(monkeypatch, response)
    assert management._ai_verify("opencode", "dummy-key-for-test") == "unknown"
    assert client.calls == [("https://opencode.ai/console/api/v1/models", {
        "Accept": "application/json", "Authorization": "Bearer dummy-key-for-test"})]


def test_zen_rejects_public_openai_list_shape(monkeypatch):
    patch_http(monkeypatch, SimpleNamespace(status_code=200, json=lambda: {
        "data": [{"id": "public-model"}]}))
    with pytest.raises(HTTPException) as exc:
        management._ai_verify("opencode", "dummy-key-for-test")
    assert exc.value.status_code == 503


def test_go_rejects_200_without_authenticated_usage_meters(monkeypatch):
    patch_http(monkeypatch, SimpleNamespace(status_code=200, json=lambda: {
        "opencode": {"id": "opencode", "models": {"example": {}}}}))
    with pytest.raises(HTTPException) as exc:
        management._ai_verify("opencode-go", "dummy-key-for-test")
    assert exc.value.status_code == 503


def test_go_accepts_real_authenticated_usage_meters(monkeypatch):
    response = SimpleNamespace(status_code=200, json=lambda: {
        "usage": {
            "rolling": {"status": "ok", "percent": 0},
            "weekly": {"status": "rate-limited", "percent": 100},
            "monthly": {"status": "ok", "percent": 10}}})
    client = patch_http(monkeypatch, response)
    assert management._ai_verify("opencode-go", "dummy-key-for-test") == "unknown"
    assert client.calls[0][0] == "https://opencode.ai/inference/go/v1/usage"


@pytest.mark.parametrize("provider,status,expected", [
    ("opencode", 401, 422),
    ("opencode-go", 403, 403),
    ("openai", 401, 422),
    ("deepseek", 429, 429),
])
def test_failed_authentication_never_succeeds(monkeypatch, provider, status, expected):
    patch_http(monkeypatch, SimpleNamespace(status_code=status))
    with pytest.raises(HTTPException) as exc:
        management._ai_verify(provider, "dummy-key-for-test")
    assert exc.value.status_code == expected


def test_unknown_pi_provider_key_never_reaches_db_storage(monkeypatch):
    monkeypatch.setattr(management, "_ai_schema", lambda db: None)
    monkeypatch.setattr(management, "_ai_pi_supported_providers",
                        lambda db: [{"id": "supported-but-no-verifier"}])
    monkeypatch.setattr(management.credentials, "available", lambda: True)

    class FakeDB:
        def scalar(self, *args, **kwargs):
            return None
        def add(self, *args, **kwargs):
            raise AssertionError("Must not save unverified key")
        def commit(self):
            raise AssertionError("Must not commit unverified key")

    with pytest.raises(HTTPException) as exc:
        management._ai_save(SimpleNamespace(
            provider_id="supported-but-no-verifier",
            api_key="dummy-key-for-test"),
            SimpleNamespace(id="account-id"), FakeDB())
    assert exc.value.status_code == 422


def test_verified_connection_payload_preserves_existing_contract():
    item = management._ai_connection_payload(SimpleNamespace(
        id="connection-id", provider_id="openai", auth_status="verified",
        credit_status="unknown", last4="last", verified_at="some-date"))
    assert item["connected"] is True
    assert item["verified"] is True


def test_nvidia_verifies_account_without_inference(monkeypatch):
    client = patch_http(monkeypatch, SimpleNamespace(
        status_code=200, json=lambda: {"user": {"id": "account-id"}}))
    assert management._ai_verify("nvidia", "dummy-key-for-test") == "unknown"
    assert client.calls == [("https://api.ngc.nvidia.com/v2/users/me", {
        "Accept": "application/json", "Authorization": "Bearer dummy-key-for-test",
    })]


@pytest.mark.parametrize("status,expected", [(401, 422), (403, 403), (402, 402), (429, 429), (503, 503)])
def test_nvidia_rejects_failed_account_verification(monkeypatch, status, expected):
    patch_http(monkeypatch, SimpleNamespace(status_code=status))
    with pytest.raises(HTTPException) as exc:
        management._ai_verify("nvidia", "dummy-key-for-test")
    assert exc.value.status_code == expected


def test_nvidia_verification_failure_prevents_key_persistence(monkeypatch):
    monkeypatch.setattr(management, "_ai_schema", lambda db: None)
    monkeypatch.setattr(management, "_ai_pi_supported_providers",
                        lambda db: [{"id": "nvidia"}])
    monkeypatch.setattr(management.credentials, "available", lambda: True)
    patch_http(monkeypatch, SimpleNamespace(status_code=403))
    class FakeDB:
        def scalar(self, *args, **kwargs): return None
        def add(self, *args, **kwargs):
            raise AssertionError("Must not save NVIDIA key")
        def commit(self):
            raise AssertionError("Must not commit NVIDIA key")
    with pytest.raises(HTTPException) as exc:
        management._ai_save(SimpleNamespace(provider_id="nvidia",
             api_key="dummy-key-for-test"), SimpleNamespace(id="account-id"), FakeDB())
    assert exc.value.status_code == 403



def test_nvidia_catalog_is_not_proof_of_authentication(monkeypatch):
    patch_http(monkeypatch, SimpleNamespace(status_code=200, json=lambda: {
        "data": [{"id": "nvidia/nv-embed-qa"}]}))
    with pytest.raises(HTTPException) as exc:
        management._ai_verify("nvidia", "dummy-key-for-test")
    assert exc.value.status_code == 503


def test_admin_curated_model_policy_filters_execution_not_just_ui():
    rules = {
        "allowed_models": [], "hidden_models": {}, "hidden_providers": [],
        "selected_models": {"nvidia": ["model-a"]}}
    assert management._ai_personal_allowed(None, "nvidia", "model-a", rules=rules)
    assert not management._ai_personal_allowed(None, "nvidia", "model-b", rules=rules)
    assert management._ai_personal_allowed(None, "openai", "model-b", rules=rules)
    assert not management._ai_allowed(None, "nvidia", "model-b", rules=rules)


def test_admin_can_disable_all_models_for_one_provider():
    rules = {"allowed_models": [], "hidden_models": {}, "hidden_providers": [],
             "selected_models": {"nvidia": []}}
    assert not management._ai_personal_allowed(None, "nvidia", "any", rules=rules)
    assert management._ai_personal_allowed(None, "deepseek", "any", rules=rules)


def test_customer_catalog_shows_all_price_types_without_admin_selection(monkeypatch):
    rows = [
        SimpleNamespace(provider_id="groq", model_id="free", name="Free",
                        details_json='{"cost":{"input":0,"output":0}}'),
        SimpleNamespace(provider_id="groq", model_id="paid", name="Paid",
                        details_json='{"cost":{"input":1,"output":2}}'),
        SimpleNamespace(provider_id="groq", model_id="unknown", name="Unknown",
                        details_json="{}"),
    ]

    def read_catalog(db, provider_id, *, refresh=False):
        assert provider_id == "groq"
        assert refresh is False
        return rows

    monkeypatch.setattr(management, "_ai_catalog_models", read_catalog)
    result = management.ai_customer_provider_model_catalog("groq", db=None)
    assert result["count"] == 3
    assert [model["price_type"] for model in result["models"]] == ["free", "paid", "unknown"]
    assert all("selected" not in model for model in result["models"])


def test_budget_policy_modes_default_on():
    from app.models.platform import PlatformPolicy
    policy = PlatformPolicy(allowed_providers="[]", allowed_models="[]",
                            allowed_tools="[]", require_tool_approval=True)
    payload = policy.as_payload()
    assert payload["budget_modes"] == {"analysis": True, "execution": True}
    policy.allowed_models = '{"budget_modes":{"analysis":false,"execution":false}}'
    assert policy.as_payload()["budget_modes"] == {"analysis": True, "execution": True}


def test_budget_modes_are_independent_and_preserve_admin_model_selection():
    from app.models.platform import PlatformPolicy
    policy = PlatformPolicy(allowed_providers="[]",
                            allowed_models='{"budget_modes":{"analysis":true,"execution":false},"selected":{"deepseek":["model-a"]}}',
                            allowed_tools="[]", require_tool_approval=True)
    payload = policy.as_payload()
    assert payload["budget_modes"] == {"analysis": True, "execution": False}
    assert payload["selected_models"] == {"deepseek": ["model-a"]}
    assert management._ai_personal_allowed(None, "deepseek", "model-a", rules=payload)
    assert not management._ai_personal_allowed(None, "deepseek", "model-b", rules=payload)


def test_budget_estimates_require_known_input_and_output_prices():
    known = SimpleNamespace(provider_id="deepseek", model_id="model-a",
                            details_json='{"cost":{"input":0.15,"output":0.6},"maxTokens":4096,"reasoning":true}')
    unknown = SimpleNamespace(provider_id="deepseek", model_id="model-b",
                              details_json='{"cost":{"input":0.15}}')
    free = SimpleNamespace(provider_id="openrouter", model_id="model-c:free",
                           details_json='{"cost":{"input":0,"output":0}}')
    priced = management._ai_model_display_info(known)
    partial = management._ai_model_display_info(unknown)
    zero = management._ai_model_display_info(free)
    assert priced["has_input_output_rates"] and priced["price_type"] == "paid"
    assert priced["max_output_tokens"] == 4096
    assert priced["reasoning"] is True
    assert not partial["has_input_output_rates"]
    assert partial["price_type"] == "paid"  # Input price is known, full estimate is not.
    assert zero["price_type"] == "free"


def test_budget_approval_signature_binds_account_session_project_and_request():
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("Node runtime unavailable")

    source = Path(__file__).resolve().parents[2] / "integration" / "pi-central.mjs"
    check = """
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createHash, createHmac, randomBytes} from 'node:crypto';
const source=fs.readFileSync(process.argv[1],'utf8');
const start=source.indexOf('const budgetApprovalSecret=');
const end=source.indexOf('function budgetProjectInventory(',start);
const sign=vm.runInNewContext(
  source.slice(start,end)+';budgetApprovalSignature',{createHash,createHmac,randomBytes});
const scope={account:{origin:'https://example.test',auth_session_id:'auth-a'},
  userId:'account-a',workspaceId:'workspace-a',projectId:'project-a'};
const request={model:{providerID:'test',modelID:'planner'},
  budget:{mode:'analysis',approvalId:'approval-a',approvedAt:100,
    estimatedInput:10,estimatedOutput:20,planId:'plan-a'},
  parts:[{type:'text',text:'read example'}]};
const original=sign(scope,'session-a',request);
assert.equal(sign(scope,'session-a',request),original);
for(const key of ['userId','workspaceId','projectId'])
  assert.notEqual(sign({...scope,[key]:'changed'},'session-a',request),original);
assert.notEqual(sign({...scope,account:{...scope.account,auth_session_id:'auth-b'}},
  'session-a',request),original);
assert.notEqual(sign(scope,'session-b',request),original);
for(const change of [
  {model:{...request.model,modelID:'builder'}},
  {budget:{...request.budget,planId:'plan-b'}},
  {parts:[{type:'text',text:'change example'}]}
]) assert.notEqual(sign(scope,'session-a',{...request,...change}),original);
"""
    result = subprocess.run([node, "--input-type=module", "-e", check, str(source)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr


def test_budget_file_scope_rejects_another_project_and_filesystem_links(tmp_path):
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("Node runtime unavailable")

    source = Path(__file__).resolve().parents[2] / "integration" / "pi-central.mjs"
    check = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
const source=fs.readFileSync(process.argv[1],'utf8');
const root=process.argv[2], directory=path.join(root,'account-a');
const other=path.join(root,'account-b');
for(const dir of [directory,other])fs.mkdirSync(dir);
const target=path.join(other,'note.txt');
fs.writeFileSync(target,'account b');
fs.linkSync(target,path.join(directory,'hard.txt'));
fs.symlinkSync(target,path.join(directory,'link.txt'));
fs.symlinkSync(other,path.join(directory,'foreign'));
const context={path,process,randomUUID,...fs,fsConstants:fs.constants};
const prelude=source.slice(source.indexOf('function withWorkspaceDirectory('),
  source.indexOf('\nfunction ',source.indexOf('function withWorkspaceDirectory(')+1));
const start=source.indexOf('function budgetPathValid(');
const end=source.indexOf('function latestBudgetPlan(',start);
const {parseBudgetPlan,writeBudgetFile}=vm.runInNewContext(
  prelude+source.slice(start,end)+';({parseBudgetPlan,writeBudgetFile})',context);
const scope={directory};
const allowed=new Set(['ok.txt','link.txt','hard.txt','foreign/note.txt']);
for(const file of ['../account-b/note.txt','src/*','.env','missing/../ok.txt'])
  assert.equal(parseBudgetPlan(JSON.stringify({summary:'Changes',files:[file]})),null);
for(const file of ['unlisted.txt','../account-b/note.txt','link.txt','hard.txt','foreign/note.txt'])
  assert.throws(()=>writeBudgetFile(scope,allowed,path.join(directory,file),'changed'));
writeBudgetFile(scope,allowed,path.join(directory,'ok.txt'),'allowed');
assert.equal(fs.readFileSync(path.join(directory,'ok.txt'),'utf8'),'allowed');
assert.equal(fs.readFileSync(target,'utf8'),'account b');
assert.equal(fs.existsSync(path.join(directory,'unlisted.txt')),false);
"""
    result = subprocess.run([node, "--input-type=module", "-e", check, str(source), str(tmp_path)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
