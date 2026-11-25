"""Setup wizard engine: gives a repository a merge app ("Ship it") with short-lived keys, in about four clicks.

The person clicks:
  1. Connect GitHub: a pre-filled page for a one-day setup key; they paste it back.
  2. Create the app: a pre-filled GitHub page; they click "Create GitHub App".
  3. Install: they pick the repository and click "Install".
The engine then does the rest through GitHub's API: the protected "ship-it" environment (main only), the app ID and
the app's private key (encrypted, never written to disk or shown), the app's entry on the merge rule's bypass list,
and a check that the app can mint a key for the repository.

Every action is a plain function; `api` is injected so the whole flow runs against a stand-in in tests.
Python 3.9 compatible (macOS Command Line Tools).
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import subprocess
import tempfile
import time
import urllib.parse
from typing import Callable, Dict, List, Optional, Tuple

API = "https://api.github.com"
ENVIRONMENT = "ship-it"
SECRET_NAME = "SHIPIT_APP_KEY"
VARIABLE_NAME = "SHIPIT_APP_ID"
# What the one-day setup key may do, and nothing else (fine-grained key, this repository only).
SETUP_KEY_PERMISSIONS = {"administration": "write", "environments": "write", "secrets": "write",
                         "variables": "write"}
APP_PERMISSIONS = {"contents": "write", "pull_requests": "write"}

Api = Callable[[str, str, Optional[str], Optional[dict]], Tuple[int, object]]


class SetupError(Exception):
    """A plain-English problem with what to do next."""


# ------------------------------------------------------------------------------------------------- HTTP
def real_api(method: str, path: str, token: Optional[str], body: Optional[dict] = None) -> Tuple[int, object]:
    """GitHub REST call with curl (macOS's own Python can fail on HTTPS certificates; curl does not)."""
    args = ["curl", "-sS", "-X", method, "-H", "Accept: application/vnd.github+json",
            "-H", "X-GitHub-Api-Version: 2022-11-28", "-w", "\n%{http_code}", API + path]
    headers_file = None
    if token:
        # The key goes in a header file, never on the command line where other programs could read it.
        fd, headers_file = tempfile.mkstemp()
        os.write(fd, f"Authorization: Bearer {token}\n".encode())
        os.close(fd)
        args[1:1] = ["-H", f"@{headers_file}"]
    if body is not None:
        args[1:1] = ["-H", "Content-Type: application/json", "--data-binary", "@-"]
    try:
        out = subprocess.run(args, input=json.dumps(body).encode() if body is not None else None,
                             capture_output=True, timeout=60).stdout.decode()
    finally:
        if headers_file:
            os.remove(headers_file)
    text, _, code = out.rpartition("\n")
    try:
        return int(code), (json.loads(text) if text.strip() else {})
    except ValueError:
        return int(code or 0), {"message": text[:200]}


def ok(result: Tuple[int, object], what: str, fix: str) -> object:
    status, data = result
    if status >= 300:
        msg = data.get("message") if isinstance(data, dict) else ""
        raise SetupError(f"{what} failed (GitHub said {status}: {msg}). {fix}")
    return data


# ------------------------------------------------------------------------------------------------- step 1
def setup_key_url(owner: str, days: int = 1) -> str:
    """GitHub's pre-filled page for a fine-grained key that expires after `days`."""
    params = {"name": "Setup wizard (one day)", "description": "Sets up the Ship it app; delete after use",
              "target_name": owner, "expires_in": str(days), **SETUP_KEY_PERMISSIONS}
    return "https://github.com/settings/personal-access-tokens/new?" + urllib.parse.urlencode(params)


def check_setup_key(api: Api, repo: str, token: str) -> dict:
    """The key works, belongs to an admin of the repository, and can manage environments."""
    if not token or len(token) < 20 or any(c.isspace() for c in token):
        raise SetupError("That does not look like a GitHub key. Copy the whole key from GitHub and paste it again.")
    user = ok(api("GET", "/user", token, None), "Reading your account", "Paste the key again or create a new one.")
    data = ok(api("GET", f"/repos/{repo}", token, None), "Reading the repository",
              f"When creating the key, choose 'Only select repositories' and pick {repo.split('/')[1]}.")
    if not (data.get("permissions") or {}).get("admin"):
        raise SetupError("This key cannot change the repository's settings. Create it with an account that is an "
                         "admin of the repository.")
    ok(api("GET", f"/repos/{repo}/environments", token, None), "Reading the repository's environments",
       "Create the key again from the Connect button: it needs the permissions that page fills in.")
    return {"login": user.get("login"), "default_branch": data.get("default_branch", "main")}


# ------------------------------------------------------------------------------------------------- step 2
def manifest(app_name: str, repo: str, base_url: str) -> dict:
    """The pre-filled app GitHub shows on 'Create GitHub App'. No webhook: the app only acts when the workflow
    asks it to."""
    return {"name": app_name, "url": f"https://github.com/{repo}", "public": False,
            "redirect_url": f"{base_url}/created", "setup_url": f"{base_url}/installed",
            "default_permissions": APP_PERMISSIONS, "default_events": [],
            "description": "Merges a pull request after the owner ticks Ship it and the tests pass."}


def create_app_form(owner: str, app_name: str, repo: str, base_url: str, state: str) -> str:
    """A page that sends the person straight to GitHub's pre-filled 'Create GitHub App' page for the organisation."""
    action = (f"https://github.com/organizations/{urllib.parse.quote(owner)}/settings/apps/new?"
              + urllib.parse.urlencode({"state": state}))
    value = json.dumps(manifest(app_name, repo, base_url)).replace("&", "&amp;").replace('"', "&quot;")
    return ("<!doctype html><meta charset='utf-8'><title>Opening GitHub</title>"
            f"<form id='f' method='post' action='{action}'><input type='hidden' name='manifest' value=\"{value}\">"
            "<noscript><button>Continue to GitHub</button></noscript></form>"
            "<script>document.getElementById('f').submit()</script>")


def convert(api: Api, code: str) -> dict:
    """Exchange GitHub's one-time code (valid one hour) for the new app's ID, name and private key."""
    if not code or not code.isalnum():
        raise SetupError("GitHub did not send a valid code back. Click Create the app again.")
    data = ok(api("POST", f"/app-manifests/{code}/conversions", None, None), "Collecting the new app",
              "The code is valid for one hour and works once: click Create the app again.")
    return {"id": data["id"], "slug": data["slug"], "pem": data["pem"], "html_url": data.get("html_url")}


def install_url(slug: str) -> str:
    return f"https://github.com/apps/{urllib.parse.quote(slug)}/installations/new"


# ------------------------------------------------------------------------------------------------- step 4
def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def app_jwt(app_id: int, pem: str) -> str:
    now = int(time.time())
    head = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64url(json.dumps({"iat": now - 60, "exp": now + 540, "iss": str(app_id)}).encode())
    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, pem.encode())
        os.close(fd)
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", path], input=f"{head}.{claims}".encode(),
                             capture_output=True, check=True, timeout=30).stdout
    finally:
        os.remove(path)
    return f"{head}.{claims}.{b64url(sig)}"


def seal(public_key_b64: str, value: str) -> str:
    """Encrypt a secret for GitHub (libsodium sealed box), as GitHub's API requires."""
    try:
        from nacl import encoding, public  # type: ignore
    except ImportError:
        raise SetupError("The encryption helper (PyNaCl) is missing. The packaged app includes it; when running "
                         "from source, install it first.") from None
    box = public.SealedBox(public.PublicKey(public_key_b64.encode(), encoding.Base64Encoder()))
    return base64.b64encode(box.encrypt(value.encode())).decode()


def find_merge_rule(api: Api, repo: str, token: str) -> dict:
    """The repository rule that restricts updates to the default branch (only the owner merges)."""
    rules = ok(api("GET", f"/repos/{repo}/rulesets", token, None), "Reading the merge rules",
               "Check the key has the Administration permission.")
    for brief in rules or []:
        full = ok(api("GET", f"/repos/{repo}/rulesets/{brief['id']}", token, None), "Reading a merge rule", "")
        includes = ((full.get("conditions") or {}).get("ref_name") or {}).get("include") or []
        if full.get("target") == "branch" and "~DEFAULT_BRANCH" in includes and \
                any(r.get("type") == "update" for r in full.get("rules") or []):
            return full
    raise SetupError("No rule restricts merging into main, so the app needs no bypass entry. If merges should be "
                     "owner-only, add that rule first.")


def finish(api: Api, repo: str, token: str, app: dict, installation_id: Optional[str], seal_fn=None,
           jwt_fn=None, log: Callable[[str], None] = lambda s: None) -> List[dict]:
    """Everything after the clicks. Each step reports done or the problem; nothing secret is logged."""
    seal_fn = seal_fn or seal
    jwt_fn = jwt_fn or app_jwt
    results: List[dict] = []

    def step(name: str, fn):
        try:
            detail = fn() or "done"
            results.append({"step": name, "ok": True, "detail": detail})
            log(f"{name}: ok")
        except SetupError as e:
            results.append({"step": name, "ok": False, "detail": str(e)})
            log(f"{name}: {e}")
        except Exception as e:  # noqa: BLE001 - reported, never hidden
            results.append({"step": name, "ok": False, "detail": f"Unexpected problem: {type(e).__name__}"})
            log(f"{name}: unexpected {type(e).__name__}")

    env = f"/repos/{repo}/environments/{ENVIRONMENT}"
    default_branch = check_setup_key(api, repo, token)["default_branch"]

    def environment():
        ok(api("PUT", env, token, {"deployment_branch_policy": {"protected_branches": False,
                                                                "custom_branch_policies": True}}),
           "Creating the protected environment", "Check the key has the Administration permission.")
        have = ok(api("GET", f"{env}/deployment-branch-policies", token, None), "Reading the environment rule", "")
        if not any(p.get("name") == default_branch for p in (have or {}).get("branch_policies", [])):
            ok(api("POST", f"{env}/deployment-branch-policies", token, {"name": default_branch, "type": "branch"}),
               "Limiting the environment to the main branch", "")
        return f"only workflows on {default_branch} can use it"

    def variable():
        body = {"name": VARIABLE_NAME, "value": str(app["id"])}
        status, _ = api("PATCH", f"{env}/variables/{VARIABLE_NAME}", token, body)
        if status == 404:
            ok(api("POST", f"{env}/variables", token, body), "Saving the app ID", "")
        elif status >= 300:
            raise SetupError(f"Saving the app ID failed (GitHub said {status}).")

    def secret():
        key = ok(api("GET", f"{env}/secrets/public-key", token, None), "Reading the encryption key", "")
        ok(api("PUT", f"{env}/secrets/{SECRET_NAME}", token,
               {"encrypted_value": seal_fn(key["key"], app["pem"]), "key_id": key["key_id"]}),
           "Saving the app's private key", "")
        return "stored encrypted; never written to this computer"

    def bypass():
        rule = find_merge_rule(api, repo, token)
        actors = rule.get("bypass_actors") or []
        if any(a.get("actor_type") == "Integration" and a.get("actor_id") == app["id"] for a in actors):
            return "already on the list"
        actors = actors + [{"actor_id": app["id"], "actor_type": "Integration", "bypass_mode": "pull_request"}]
        body = {k: rule[k] for k in ("name", "target", "enforcement", "conditions", "rules") if k in rule}
        body["bypass_actors"] = actors
        ok(api("PUT", f"/repos/{repo}/rulesets/{rule['id']}", token, body), "Adding the app to the bypass list", "")
        return f"added to '{rule.get('name')}', for pull requests only"

    def can_mint():
        jwt = jwt_fn(app["id"], app["pem"])
        inst = ok(api("GET", f"/repos/{repo}/installation", jwt, None), "Finding the app's installation",
                  "Click Install and pick the repository.")
        if installation_id and str(inst.get("id")) != str(installation_id):
            raise SetupError("The app is installed somewhere other than where GitHub sent us back from.")
        tok = ok(api("POST", f"/app/installations/{inst['id']}/access_tokens", jwt,
                     {"repositories": [repo.split("/")[1]], "permissions": APP_PERMISSIONS}),
                 "Test key for the repository", "")
        return f"test key issued, expires {tok.get('expires_at', 'within an hour')}"

    step("Protected environment", environment)
    step("App ID", variable)
    step("App private key", secret)
    step("Bypass entry on the merge rule", bypass)
    step("App can act on the repository", can_mint)
    return results


def new_state() -> str:
    return secrets.token_urlsafe(16)
