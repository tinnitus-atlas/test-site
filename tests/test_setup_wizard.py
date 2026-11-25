"""Setup wizard: four clicks for the owner; everything else through GitHub's API, against a stand-in GitHub."""
import json
import shutil
import subprocess
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from tools.launcher.setup_wizard import engine, server

ROOT = Path(__file__).resolve().parents[1]
REPO = "acme/site"
GOOD = "github_pat_" + "x" * 40


class FakeGitHub:
    def __init__(self, admin=True, rule=True):
        self.calls, self.admin, self.rule = [], admin, rule
        self.ruleset = {"id": 9, "name": "Only the owner merges", "target": "branch", "enforcement": "active",
                        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                        "rules": [{"type": "update"}],
                        "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}]}

    def __call__(self, method, path, token, body=None):
        self.calls.append((method, path, token, body))
        if path == "/user":
            return (200, {"login": "owner"}) if token == GOOD else (401, {"message": "Bad credentials"})
        if path == f"/repos/{REPO}" and method == "GET":
            return 200, {"default_branch": "main", "permissions": {"admin": self.admin}}
        if path == f"/repos/{REPO}/environments" and method == "GET":
            return 200, {"environments": []}
        if path.startswith("/app-manifests/"):
            return 201, {"id": 4242, "slug": "site-ship-it", "pem": "-----BEGIN RSA PRIVATE KEY-----\nSECRET\n",
                         "html_url": "https://github.com/apps/site-ship-it"}
        if path.endswith("/deployment-branch-policies") and method == "GET":
            return 200, {"branch_policies": []}
        if path.endswith(f"/variables/{engine.VARIABLE_NAME}") and method == "PATCH":
            return 404, {"message": "Not Found"}
        if path.endswith("/secrets/public-key"):
            return 200, {"key": "cHVibGlj", "key_id": "k1"}
        if path == f"/repos/{REPO}/rulesets" and method == "GET":
            return 200, [{"id": 9}] if self.rule else []
        if path == f"/repos/{REPO}/rulesets/9" and method == "GET":
            return 200, self.ruleset
        if path == f"/repos/{REPO}/installation":
            return 200, {"id": 77}
        if path.endswith("/access_tokens"):
            return 201, {"token": "ghs_test", "expires_at": "2026-11-25T12:00:00Z"}
        return 200 if method != "POST" else 201, {}


def run_finish(gh, **kw):
    app = {"id": 4242, "slug": "site-ship-it", "pem": "-----BEGIN RSA PRIVATE KEY-----\nSECRET\n"}
    return engine.finish(gh, REPO, GOOD, app, "77", seal_fn=lambda k, v: "SEALED", jwt_fn=lambda i, p: "JWT", **kw)


def test_setup_key_page_is_prefilled_with_only_the_needed_permissions():
    url = engine.setup_key_url("acme")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert url.startswith("https://github.com/settings/personal-access-tokens/new?")
    assert q["target_name"] == "acme" and q["expires_in"] == "1"
    assert {k: v for k, v in q.items() if v in ("read", "write")} == engine.SETUP_KEY_PERMISSIONS


def test_setup_key_must_belong_to_an_admin():
    with pytest.raises(engine.SetupError, match="admin"):
        engine.check_setup_key(FakeGitHub(admin=False), REPO, GOOD)
    with pytest.raises(engine.SetupError, match="does not look like"):
        engine.check_setup_key(FakeGitHub(), REPO, "short")
    with pytest.raises(engine.SetupError, match="Reading your account"):
        engine.check_setup_key(FakeGitHub(), REPO, "github_pat_" + "y" * 40)


def test_app_has_no_webhook_and_only_contents_and_pull_requests():
    m = engine.manifest("site-ship-it", REPO, "http://127.0.0.1:8765")
    assert m["default_permissions"] == {"contents": "write", "pull_requests": "write"}
    assert "hook_attributes" not in m and m["public"] is False
    assert m["redirect_url"] == "http://127.0.0.1:8765/created" and m["setup_url"] == "http://127.0.0.1:8765/installed"
    form = engine.create_app_form("acme", "site-ship-it", REPO, "http://127.0.0.1:8765", "st8")
    assert "https://github.com/organizations/acme/settings/apps/new?state=st8" in form


def test_finish_does_every_step_and_the_key_is_only_sent_encrypted():
    gh = FakeGitHub()
    results = run_finish(gh)
    assert all(r["ok"] for r in results), results
    sent = json.dumps([c[3] for c in gh.calls])
    assert "SECRET" not in sent and "SEALED" in sent
    env_put = next(c for c in gh.calls if c[0] == "PUT" and c[1].endswith("/environments/ship-it"))
    assert env_put[3]["deployment_branch_policy"]["custom_branch_policies"] is True
    assert any(c[0] == "POST" and c[1].endswith("/deployment-branch-policies") and c[3]["name"] == "main" for c in gh.calls)
    put_rule = next(c for c in gh.calls if c[0] == "PUT" and c[1].endswith("/rulesets/9"))
    assert {"actor_id": 4242, "actor_type": "Integration", "bypass_mode": "pull_request"} in put_rule[3]["bypass_actors"]
    assert {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"} in put_rule[3]["bypass_actors"]
    token_req = next(c for c in gh.calls if c[1].endswith("/access_tokens"))
    assert token_req[2] == "JWT" and token_req[3]["repositories"] == ["site"]


def test_running_finish_twice_does_not_add_the_bypass_entry_twice():
    gh = FakeGitHub()
    gh.ruleset["bypass_actors"].append({"actor_id": 4242, "actor_type": "Integration", "bypass_mode": "pull_request"})
    results = run_finish(gh)
    assert next(r for r in results if r["step"].startswith("Bypass"))["detail"] == "already on the list"
    assert not any(c[0] == "PUT" and c[1].endswith("/rulesets/9") for c in gh.calls)


def test_a_failing_step_is_reported_and_the_others_still_run():
    gh = FakeGitHub(rule=False)
    results = run_finish(gh)
    bad = [r for r in results if not r["ok"]]
    assert len(bad) == 1 and "No rule restricts merging" in bad[0]["detail"]
    assert results[-1]["ok"]


@pytest.mark.skipif(not shutil.which("openssl"), reason="openssl not installed")
def test_app_key_signs_a_jwt(tmp_path):
    key = tmp_path / "k.pem"
    subprocess.run(["openssl", "genrsa", "-out", str(key), "2048"], check=True, capture_output=True)
    assert engine.app_jwt(4242, key.read_text()).count(".") == 2


def test_seal_matches_what_github_can_decrypt():
    nacl = pytest.importorskip("nacl.public")
    import base64
    from nacl import encoding
    sk = nacl.PrivateKey.generate()
    pub = sk.public_key.encode(encoding.Base64Encoder()).decode()
    sealed = engine.seal(pub, "the-key")
    assert nacl.SealedBox(sk).decrypt(base64.b64decode(sealed)) == b"the-key"


@pytest.fixture
def wizard():
    gh = FakeGitHub()
    st = server.State(REPO, "site-ship-it", 0, api=gh)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(st))
    st.port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield st, gh, f"http://127.0.0.1:{st.port}"
    httpd.shutdown()


def get(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_whole_flow_through_the_page(wizard, monkeypatch):
    st, gh, base = wizard
    monkeypatch.setattr(engine, "seal", lambda k, v: "SEALED")
    monkeypatch.setattr(engine, "app_jwt", lambda i, p: "JWT")
    code, page = get(base + "/")
    assert code == 200 and st.launch in page
    assert post(f"{base}/api/connect?t={st.launch}", {"key": GOOD})[1]["connected"]
    code, form = get(f"{base}/create?t={st.launch}")
    assert code == 200 and st.state in form
    get(f"{base}/created?code=abc123&state={st.state}")
    get(f"{base}/installed?installation_id=77&setup_action=install")
    code, status = post(f"{base}/api/finish?t={st.launch}", {})
    assert code == 200 and status["done"], status
    assert "pem" not in json.dumps(status) and st.setup_key is None and "pem" not in st.app
    assert "SECRET" not in "\n".join(st.log)


def test_page_api_refuses_other_pages_and_returns_from_other_setups(wizard):
    st, gh, base = wizard
    assert post(f"{base}/api/connect?t=wrong", {"key": GOOD})[0] == 403
    assert get(f"{base}/api/status?t=wrong")[0] == 404
    code, page = get(f"{base}/created?code=abc123&state=other")
    assert "does not belong" in page and st.app is None
    assert get(f"{base}/", headers={"Host": "evil.example"})[0] == 403


def test_wizard_source_is_publish_clean():
    import re
    for f in (ROOT / "tools" / "launcher" / "setup_wizard").glob("*"):
        if f.suffix in (".py", ".html"):
            text = f.read_text()
            assert not re.search(r"/Users/[a-z]|/home/[a-z]|tinnitus|varioso", text, re.I), f
