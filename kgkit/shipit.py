"""Ship it: merges a pull request for the owner once the owner has ticked its "Ship it" box and the tests pass.

The owner ticks one box and walks away. This module then keeps the pull request up to date with main, waits for the
tests and merges it. It never merges anything the owner has not approved:

- Approval is the owner's own edit that turns the box from unticked to ticked (checked from the event, not from the
  box alone). The approved commit is recorded in a comment written by the Ship it app, which nobody else can write.
- Commits added after the approval keep it only if they are the app's own "bring up to date with main" merges, or, on
  a review pull request, the review sync's commit that touches only records/. Anything else voids the approval and
  the owner is asked to tick again.
- Pull requests that change .github/workflows are never merged here: they need the owner's manual merge.
- The app's keys are minted per run, last one hour, and are limited to this repository with contents and pull
  request write access.

Usage (from the workflow): python3 -m kgkit.shipit
Environment: GITHUB_REPOSITORY, GITHUB_EVENT_NAME, GITHUB_EVENT_PATH, GH_READ_TOKEN (the built-in token, read only),
SHIPIT_APP_ID, SHIPIT_APP_KEY, REVIEW_OWNER, REVIEW_BOT.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
BOX = re.compile(r"^- \[([ xX])\] \*{0,2}Ship it\b", re.M)
MARK = re.compile(r"<!-- ship-it (\w+)=([0-9a-f]{7,40}|[\w-]+) -->")
SYNC_MESSAGE = "Ticked items ready to go live with the merge"
SHIP_LINE = ("- [ ] **Ship it**: tick when you are done here. The pull request is then brought up to date, "
             "tested and merged for you.")


def ticked(body: str | None) -> bool:
    m = BOX.search(body or "")
    return bool(m and m.group(1) in "xX")


def is_review_pr(pr: dict, bot: str) -> bool:
    return pr["user"]["login"] == bot and pr["title"].startswith("Nightly proposals")


def trusted(commit: dict, pr: dict, app_login: str, bot: str) -> bool:
    """A commit added after the approval that keeps the approval valid."""
    author = (commit.get("author") or {}).get("login")
    parents = commit.get("parents") or []
    verified = ((commit.get("commit") or {}).get("verification") or {}).get("verified")
    if author == app_login and len(parents) == 2 and verified:
        return True                                   # the app's own update merge from main
    message = ((commit.get("commit") or {}).get("message") or "").strip()
    files = [f["filename"] for f in commit.get("files") or []]
    return (is_review_pr(pr, bot) and message == SYNC_MESSAGE and bool(files)
            and all(f.startswith("records/") for f in files))


def decide(pr: dict, *, approved: str | None, new_commits: list[dict], tick_event: bool, touches_workflows: bool,
           tests: str | None, sync_running: bool, app_login: str, bot: str) -> tuple[str, str]:
    """Next step for one pull request: (action, detail). Actions: skip, approve, note, wait, update, merge."""
    head = pr["head"]["sha"]
    if not ticked(pr.get("body")):
        return "skip", "box not ticked"
    if pr.get("draft") or pr["head"]["repo"] is None or pr["head"]["repo"]["full_name"] != pr["base"]["repo"]["full_name"]:
        return "skip", "draft or from another repository"
    if touches_workflows:
        return "note", "workflows"
    if tick_event and approved != head:
        return "approve", head
    if not approved:
        return "skip", "ticked, but not by the owner"
    if approved != head:
        if new_commits and all(trusted(c, pr, app_login, bot) for c in new_commits):
            return "approve", head
        return "note", f"void-{head[:12]}"
    if sync_running:
        return "wait", "review sync running"
    state = pr.get("mergeable_state")
    if state in (None, "unknown"):
        return "wait", "GitHub is still checking the pull request"
    if state == "dirty":
        return "note", f"conflict-{head[:12]}"
    if state == "behind":
        return "update", head
    if tests is None or tests == "pending":
        return "wait", "tests running"
    if tests != "success":
        return "note", f"failed-{head[:12]}"
    return "merge", head


NOTES = {
    "workflows": "Ship it does not merge pull requests that change the automation workflows. Please merge this one "
                 "yourself.",
    "void": "New commits arrived after you ticked Ship it, so nothing will be merged. Untick and tick Ship it again "
            "to approve the latest version.",
    "conflict": "This pull request conflicts with main, so it cannot be merged yet. The conflict will be resolved on "
                "the branch; tick Ship it again afterwards.",
    "failed": "The tests failed on the latest version, so it was not merged. It will be fixed on the branch; tick "
              "Ship it again afterwards.",
    "refused": "GitHub refused the merge. The Ship it app is probably not on the bypass list of the repository rule "
               "that only lets the owner merge; see docs/ship-it.md.",
}


# ---------------------------------------------------------------------------------------------------- GitHub calls
def call(method: str, path: str, token: str, body: dict | None = None, auth: str = "Bearer"):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"{auth} {token}", "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ship-it"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path.split('?')[0]} failed: HTTP {e.code}") from None


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def app_jwt(app_id: str, key_pem: str) -> str:
    now = int(time.time())
    head = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64(json.dumps({"iat": now - 60, "exp": now + 540, "iss": app_id}).encode())
    with tempfile.NamedTemporaryFile("w", delete=False, dir=os.environ.get("RUNNER_TEMP")) as f:
        os.chmod(f.name, 0o600)
        f.write(key_pem.replace("\\n", "\n"))
        path = f.name
    try:
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", path], input=f"{head}.{claims}".encode(),
                             capture_output=True, check=True).stdout
    finally:
        os.remove(path)
    return f"{head}.{claims}.{b64(sig)}"


def app_token(repo: str, app_id: str, key_pem: str) -> tuple[str, str]:
    """A one-hour key limited to this repository, contents and pull requests. Returns (token, app bot login)."""
    jwt = app_jwt(app_id, key_pem)
    app = call("GET", "/app", jwt)
    inst = call("GET", f"/repos/{repo}/installation", jwt)
    tok = call("POST", f"/app/installations/{inst['id']}/access_tokens", jwt,
               {"repositories": [repo.split("/")[1]], "permissions": {"contents": "write", "pull_requests": "write"}})
    print(f"::add-mask::{tok['token']}")
    return tok["token"], f"{app['slug']}[bot]"


def record_approval(repo: str, n: int, write: str, existing: dict | None, sha: str) -> None:
    """One approval comment per pull request, written by the app and updated in place."""
    text = (f"<!-- ship-it approved={sha} -->\nShip it: approved version `{sha[:7]}`. It will be brought up to date, "
            "tested and merged without further clicks.")
    if existing:
        call("PATCH", f"/repos/{repo}/issues/comments/{existing['id']}", write, {"body": text})
    else:
        call("POST", f"/repos/{repo}/issues/{n}/comments", write, {"body": text})


def run() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    read = os.environ["GH_READ_TOKEN"]
    owner = os.environ.get("REVIEW_OWNER") or "varioso"
    bot = os.environ.get("REVIEW_BOT") or "varioso-bot"
    if not os.environ.get("SHIPIT_APP_ID") or not os.environ.get("SHIPIT_APP_KEY"):
        print("Ship it is not set up yet (SHIPIT_APP_ID or SHIPIT_APP_KEY missing); nothing done.")
        return 0
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"])) if os.environ.get("GITHUB_EVENT_PATH") else {}
    tick_pr = None
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request_target" and event.get("action") == "edited":
        before = ((event.get("changes") or {}).get("body") or {}).get("from")
        pr = event["pull_request"]
        if event["sender"]["login"] == owner and before is not None and not ticked(before) and ticked(pr["body"]):
            tick_pr = pr["number"]
    write, app_login = app_token(repo, os.environ["SHIPIT_APP_ID"], os.environ["SHIPIT_APP_KEY"])
    summary = []
    for brief in call("GET", f"/repos/{repo}/pulls?state=open&per_page=50", read):
        if not ticked(brief.get("body")):
            continue
        n = brief["number"]
        pr = call("GET", f"/repos/{repo}/pulls/{n}", read)
        comments = [c for c in call("GET", f"/repos/{repo}/issues/{n}/comments?per_page=100", read)
                    if c["user"]["login"] == app_login]
        marks = [(c, m) for c in comments for m in MARK.finditer(c["body"] or "")]
        approved_c = next((c for c, m in reversed(marks) if m.group(1) == "approved"), None)
        approved = MARK.search(approved_c["body"]).group(2) if approved_c else None
        noted = {m.group(2) for c, m in marks if m.group(1) == "note"}
        files = call("GET", f"/repos/{repo}/pulls/{n}/files?per_page=100", read)
        touches_wf = any(f["filename"].startswith(".github/workflows/") for f in files)
        new = []
        if approved and approved != pr["head"]["sha"]:
            cmp = call("GET", f"/repos/{repo}/compare/{approved}...{pr['head']['sha']}", read)
            new = [call("GET", f"/repos/{repo}/commits/{c['sha']}", read) for c in cmp.get("commits", [])[:20]]
        runs = call("GET", f"/repos/{repo}/commits/{pr['head']['sha']}/check-runs?check_name=tests", read)
        latest = max(runs.get("check_runs", []), key=lambda r: r.get("started_at") or "", default=None)
        tests = None if latest is None else (latest.get("conclusion") or "pending")
        sync = [r for s in ("queued", "in_progress") for r in call(
            "GET", f"/repos/{repo}/actions/workflows/review-sync.yml/runs?status={s}&per_page=20", read)
            .get("workflow_runs", []) if r.get("head_branch") == pr["head"]["ref"]]
        action, detail = decide(pr, approved=approved, new_commits=new, tick_event=(n == tick_pr),
                                touches_workflows=touches_wf, tests=tests, sync_running=bool(sync),
                                app_login=app_login, bot=bot)
        if action == "approve":
            # Record it, then carry on in the same run (the tests may already have passed).
            record_approval(repo, n, write, approved_c, detail)
            action, detail = decide(pr, approved=detail, new_commits=[], tick_event=False,
                                    touches_workflows=touches_wf, tests=tests, sync_running=bool(sync),
                                    app_login=app_login, bot=bot)
            summary.append(f"#{n}: approved")
        summary.append(f"#{n}: {action} ({detail})")
        if action == "approve":
            record_approval(repo, n, write, approved_c, detail)
        elif action == "note" and detail not in noted:
            call("POST", f"/repos/{repo}/issues/{n}/comments", write,
                 {"body": f"<!-- ship-it note={detail} -->\n{NOTES[detail.split('-')[0]]}"})
        elif action == "update":
            try:
                call("PUT", f"/repos/{repo}/pulls/{n}/update-branch", write, {"expected_head_sha": detail})
            except RuntimeError as e:          # usually another run updated it a moment earlier
                summary.append(f"#{n}: update skipped ({e})")
        elif action == "merge":
            try:
                res = call("PUT", f"/repos/{repo}/pulls/{n}/merge", write,
                           {"merge_method": "squash", "sha": detail, "commit_title": f"{pr['title']} (#{n})",
                            "commit_message": "Merged by Ship it after the owner's approval."})
            except RuntimeError as e:
                summary.append(f"#{n}: merge refused ({e})")
                if call("GET", f"/repos/{repo}/pulls/{n}", read).get("merged"):
                    continue                   # another run merged it a moment earlier
                if f"refused-{detail[:12]}" not in noted:
                    call("POST", f"/repos/{repo}/issues/{n}/comments", write,
                         {"body": f"<!-- ship-it note=refused-{detail[:12]} -->\n{NOTES['refused']}"})
                continue
            call("POST", f"/repos/{repo}/issues/{n}/comments", write,
                 {"body": f"<!-- ship-it note=merged-{detail[:12]} -->\nShip it: merged as `{res.get('sha', '')[:7]}`."})
    print("\n".join(summary) or "No pull request has Ship it ticked.")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("## Ship it\n\n" + ("\n".join(f"- {s}" for s in summary) or "Nothing ticked.") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(run())
