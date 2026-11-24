"""Ship it: merges a pull request for the owner once the owner has ticked its "Ship it" box and the tests pass.

The owner ticks one box and walks away. This module then keeps the pull request up to date with main, waits for the
tests and merges it. It never merges anything the owner has not approved:

- Approval is the owner's own edit that turns the box from unticked to ticked (read from the event, not from the box).
  What is approved is the pull request's net change against main at the moment of the tick: a fingerprint of every
  changed file's content. The fingerprint is recorded in a comment that only the Ship it app can write.
- The pull request is merged only while its net change still has exactly that fingerprint. Bringing it up to date with
  main keeps the fingerprint; any other change (a new commit, a force push, a different base) voids the approval.
- Unticking by the owner revokes the approval, so nobody else can re-tick it.
- Never merged here: pull requests that change .github/, review pull requests (the owner merges those), pull requests
  not aimed at main, from another repository, drafts, or with failing tests.
- The app's keys are minted per run, last one hour, and are limited to this repository with contents and pull request
  access. The app's private key is an environment secret usable only by workflows running on main.

Usage (from the workflow): python3 -m kgkit.shipit
Environment: GITHUB_REPOSITORY, GITHUB_EVENT_NAME, GITHUB_EVENT_PATH, GH_READ_TOKEN (the built-in token, read only),
SHIPIT_APP_ID, SHIPIT_APP_KEY, REVIEW_OWNER, REVIEW_BOT.
"""
from __future__ import annotations

import base64
import hashlib
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
SHIP_TEXT = ("**Ship it**: tick when you are done here. The pull request is then brought up to date, tested and merged "
             "for you.")
SHIP_LINE = f"- [ ] {SHIP_TEXT}"
BOX = re.compile(r"^- \[([ xX])\] " + re.escape(SHIP_TEXT) + r"\s*$", re.M)
APPROVED = re.compile(r"<!-- ship-it approved=([0-9a-f]{64}) head=([0-9a-f]{40}) -->")
REVOKED = "<!-- ship-it revoked -->"
NOTE = re.compile(r"<!-- ship-it note=([\w-]+) -->")
MAX_FILES = 300          # GitHub's compare lists at most 300 files; more fails closed


def _visible(body: str) -> str:
    """The body without HTML comments and code blocks, so a box hidden there does not count."""
    body = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    return re.sub(r"^```.*?^```", "", body, flags=re.S | re.M)


def ticked(body: str | None) -> bool:
    """True only when the body holds exactly one Ship it box, outside comments and code, and it is ticked."""
    boxes = BOX.findall(_visible(body or ""))
    return len(boxes) == 1 and boxes[0] in "xX"


def is_review_pr(pr: dict, bot: str) -> bool:
    return pr["user"]["login"] == bot and pr["title"].startswith("Nightly proposals")


def fingerprint(base_ref: str, compare: dict) -> str | None:
    """Fingerprint of a pull request's net change: base branch plus every changed file's name, status and content
    hash. None when GitHub could not list every file (fails closed)."""
    files = compare.get("files")
    if files is None or len(files) >= MAX_FILES:
        return None
    rows = sorted((f["filename"], f.get("status"), f.get("sha"), f.get("previous_filename")) for f in files)
    return hashlib.sha256(json.dumps([base_ref, rows]).encode()).hexdigest()


def decide(pr: dict, *, default_branch: str, bot: str, approved: str | None, current: str | None, behind_by: int,
           touches_workflows: bool, tests: str | None) -> tuple[str, str]:
    """Next step for one pull request whose box is ticked: (action, detail).
    Actions: skip, note (detail = note key), wait, update, merge."""
    head = pr["head"]["sha"][:12]
    if pr.get("draft") or pr["head"]["repo"] is None or pr["head"]["repo"]["full_name"] != pr["base"]["repo"]["full_name"]:
        return "skip", "draft or from another repository"
    if is_review_pr(pr, bot):
        return "note", "review"
    if pr["base"]["ref"] != default_branch:
        return "note", "base"
    if touches_workflows:
        return "note", "workflows"
    if not approved:
        return "note", f"unapproved-{head}"
    if current is None:
        return "note", f"toolarge-{head}"
    if current != approved:
        return "note", f"void-{head}"
    if behind_by > 0:
        return "update", pr["head"]["sha"]
    if pr.get("mergeable_state") == "dirty" or pr.get("mergeable") is False:
        return "note", f"conflict-{head}"
    if tests is None or tests == "pending":
        return "wait", "tests running"
    if tests != "success":
        return "note", f"failed-{head}"
    return "merge", pr["head"]["sha"]


NOTES = {
    "review": "Ship it does not merge review pull requests: merge this one yourself once you have ticked the items.",
    "base": "Ship it only merges pull requests aimed at main.",
    "workflows": "Ship it does not merge pull requests that change the automation workflows. Please merge this one "
                 "yourself.",
    "unapproved": "Ship it is ticked, but no tick by the owner was recorded for this version. Untick and tick Ship it "
                  "again to approve it.",
    "toolarge": "This pull request changes too many files for Ship it to check. Please merge it yourself.",
    "void": "This pull request changed after you ticked Ship it, so nothing will be merged. Untick and tick Ship it "
            "again to approve the latest version.",
    "conflict": "This pull request conflicts with main, so it cannot be merged yet. The conflict will be resolved on "
                "the branch; then untick and tick Ship it again.",
    "failed": "The tests failed on the latest version, so it was not merged. It will be fixed on the branch; then "
              "untick and tick Ship it again.",
    "updatefailed": "Ship it could not bring this pull request up to date with main. Please update or merge it "
                    "yourself.",
    "refused": "GitHub refused the merge. The Ship it app is probably not on the bypass list of the repository rule "
               "that only lets the owner merge; see docs/ship-it.md.",
}


# ---------------------------------------------------------------------------------------------------- GitHub calls
def call(method: str, path: str, token: str, body: dict | None = None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ship-it"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path.split('?')[0]} failed: HTTP {e.code}") from None


def pages(path: str, token: str, key: str | None = None, per_page: int = 100, limit: int = 20) -> list:
    """Every page of a list endpoint (up to limit pages)."""
    out = []
    sep = "&" if "?" in path else "?"
    for page in range(1, limit + 1):
        got = call("GET", f"{path}{sep}per_page={per_page}&page={page}", token)
        items = got.get(key, []) if key else got
        out += items
        if len(items) < per_page:
            break
    return out


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


def tests_result(repo: str, sha: str, read: str) -> str | None:
    """Result of the required "tests" check from GitHub Actions on this exact commit (other apps cannot fake it)."""
    runs = [r for r in call("GET", f"/repos/{repo}/commits/{sha}/check-runs?check_name=tests&per_page=100", read)
            .get("check_runs", []) if (r.get("app") or {}).get("slug") == "github-actions"]
    if not runs:
        return None
    latest = max(runs, key=lambda r: r.get("started_at") or "")
    return latest.get("conclusion") or "pending"


def tick_change(event: dict, owner: str) -> tuple[int, str, str] | None:
    """(pull request number, "tick" or "untick", head commit at that moment) for an owner's edit that flips the box."""
    if event.get("action") != "edited" or (event.get("sender") or {}).get("login") != owner:
        return None
    before = ((event.get("changes") or {}).get("body") or {}).get("from")
    if before is None:
        return None
    pr = event["pull_request"]
    was, now = ticked(before), ticked(pr.get("body"))
    if was == now:
        return None
    return pr["number"], ("tick" if now else "untick"), pr["head"]["sha"]


class Repo:
    def __init__(self, repo: str, read: str, write: str, app_login: str):
        self.repo, self.read, self.write, self.app_login = repo, read, write, app_login

    def app_comments(self, n: int) -> list[dict]:
        return [c for c in pages(f"/repos/{self.repo}/issues/{n}/comments", self.read)
                if c["user"]["login"] == self.app_login]

    def compare(self, base: str, sha: str) -> dict:
        return call("GET", f"/repos/{self.repo}/compare/{base}...{sha}?per_page=100", self.read)

    def comment(self, n: int, text: str, existing: dict | None = None) -> None:
        if existing:
            call("PATCH", f"/repos/{self.repo}/issues/comments/{existing['id']}", self.write, {"body": text})
        else:
            call("POST", f"/repos/{self.repo}/issues/{n}/comments", self.write, {"body": text})


def approval_state(comments: list[dict]) -> tuple[dict | None, str | None]:
    """(the approval comment, the approved fingerprint or None when never approved or revoked)."""
    mine = [c for c in comments if APPROVED.search(c["body"] or "") or REVOKED in (c["body"] or "")]
    if not mine:
        return None, None
    last = mine[-1]
    m = APPROVED.search(last["body"] or "")
    return last, (m.group(1) if m else None)


def ship_one(gh: Repo, n: int, default_branch: str, bot: str, change: tuple | None, summary: list) -> None:
    pr = call("GET", f"/repos/{gh.repo}/pulls/{n}", gh.read)
    comments = gh.app_comments(n)
    approval_c, approved = approval_state(comments)
    if change and change[0] == n:
        if change[1] == "untick":
            if approval_c:
                gh.comment(n, f"{REVOKED}\nShip it: approval withdrawn.", approval_c)
            summary.append(f"#{n}: approval withdrawn")
            return
        fp = fingerprint(pr["base"]["ref"], gh.compare(default_branch, change[2]))
        if fp:
            gh.comment(n, f"<!-- ship-it approved={fp} head={change[2]} -->\nShip it: approved version "
                          f"`{change[2][:7]}`. It will be brought up to date, tested and merged without further "
                          "clicks.", approval_c)
            approved = fp
            summary.append(f"#{n}: approved")
    if not ticked(pr.get("body")):
        return
    noted = {m.group(1) for c in comments for m in NOTE.finditer(c["body"] or "")}
    cur = gh.compare(default_branch, pr["head"]["sha"])
    current = fingerprint(pr["base"]["ref"], cur)
    touches_wf = any(f["filename"].startswith(".github/") for f in cur.get("files") or [])
    tests = tests_result(gh.repo, pr["head"]["sha"], gh.read)
    action, detail = decide(pr, default_branch=default_branch, bot=bot, approved=approved, current=current,
                            behind_by=int(cur.get("behind_by") or 0), touches_workflows=touches_wf, tests=tests)
    summary.append(f"#{n}: {action} ({detail})")
    if action == "note" and detail not in noted:
        gh.comment(n, f"<!-- ship-it note={detail} -->\n{NOTES[detail.split('-')[0]]}")
    elif action == "update":
        try:
            call("PUT", f"/repos/{gh.repo}/pulls/{n}/update-branch", gh.write, {"expected_head_sha": detail})
        except RuntimeError as e:
            summary.append(f"#{n}: update failed ({e})")
            key = f"updatefailed-{detail[:12]}"
            if key not in noted:
                gh.comment(n, f"<!-- ship-it note={key} -->\n{NOTES['updatefailed']}")
    elif action == "merge":
        try:
            res = call("PUT", f"/repos/{gh.repo}/pulls/{n}/merge", gh.write,
                       {"merge_method": "squash", "sha": detail, "commit_title": f"{pr['title']} (#{n})",
                        "commit_message": "Merged by Ship it after the owner's approval."})
        except RuntimeError as e:
            summary.append(f"#{n}: merge refused ({e})")
            if call("GET", f"/repos/{gh.repo}/pulls/{n}", gh.read).get("merged"):
                return                         # another run merged it a moment earlier
            key = f"refused-{detail[:12]}"
            if key not in noted:
                gh.comment(n, f"<!-- ship-it note={key} -->\n{NOTES['refused']}")
            return
        gh.comment(n, f"<!-- ship-it note=merged-{detail[:12]} -->\nShip it: merged as `{res.get('sha', '')[:7]}`.")


def run() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    read = os.environ["GH_READ_TOKEN"]
    owner = os.environ.get("REVIEW_OWNER") or "varioso"
    bot = os.environ.get("REVIEW_BOT") or "varioso-bot"
    if not os.environ.get("SHIPIT_APP_ID") or not os.environ.get("SHIPIT_APP_KEY"):
        print("Ship it is not set up yet (SHIPIT_APP_ID or SHIPIT_APP_KEY missing); nothing done.")
        return 0
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"])) if os.environ.get("GITHUB_EVENT_PATH") else {}
    change = tick_change(event, owner) if os.environ.get("GITHUB_EVENT_NAME") == "pull_request_target" else None
    write, app_login = app_token(repo, os.environ["SHIPIT_APP_ID"], os.environ["SHIPIT_APP_KEY"])
    gh = Repo(repo, read, write, app_login)
    default_branch = call("GET", f"/repos/{repo}", read)["default_branch"]
    numbers = [p["number"] for p in pages(f"/repos/{repo}/pulls?state=open", read) if ticked(p.get("body"))]
    if change and change[0] not in numbers:
        numbers.insert(0, change[0])
    summary: list[str] = []
    failed = False
    for n in numbers:
        try:
            ship_one(gh, n, default_branch, bot, change, summary)
        except Exception as e:                 # one pull request's error must not stop the others
            failed = True
            summary.append(f"#{n}: error ({e})")
    print("\n".join(summary) or "No pull request has Ship it ticked.")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("## Ship it\n\n" + ("\n".join(f"- {s}" for s in summary) or "Nothing ticked.") + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
