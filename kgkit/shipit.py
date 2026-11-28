"""Ship it: merges a pull request for the owner once the owner has ticked its "Ship it" box and the tests pass.

The owner ticks one box and walks away. This module then keeps the pull request up to date with main, waits for the
tests and merges it. It never merges anything the owner has not approved:

- Approval is the owner's own edit that turns the box from unticked to ticked (read from the event, not from the box).
  What is approved is the pull request's net change against main at the moment of the tick: a fingerprint of every
  changed file's content. The fingerprint is recorded in a comment that only the Ship it app can write.
- The pull request is merged only while its net change still has exactly that fingerprint. Bringing it up to date with
  main keeps the fingerprint; any other change (a new commit, a force push, a different base) voids the approval.
- Unticking by the owner revokes the approval, so nobody else can re-tick it.
- Review pull requests ("Nightly proposals ..."): their branch changes after the tick because the review sync writes
  the ticked items into records/. So for them the fingerprint covers every file except records/, the approval also
  records the ticks (a later owner edit updates them; anyone else's edit voids the approval), and before merging,
  main's own review code recomputes records/ from the ticks in a scratch copy and must get exactly the branch's
  records/. Pushed data the owner did not see, or records that do not follow from the ticks, are never merged.
- Never merged here: pull requests that change .github/, pull requests not aimed at main, from another repository,
  drafts, or with failing tests.
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
APPROVED = re.compile(r"<!-- ship-it approved=([0-9a-f]{64}) head=([0-9a-f]{40})(?: body=([0-9a-f]{64}))?"
                      r"(?: mode=(review|code))? -->")
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


def fingerprint(base_ref: str, compare: dict, skip_records: bool = False) -> str | None:
    """Fingerprint of a pull request's net change: base branch plus every changed file's name, status and content
    hash (without records/ for review pull requests). None when GitHub could not list every file (fails closed)."""
    files = compare.get("files")
    if files is None or len(files) >= MAX_FILES:
        return None
    rows = sorted((f["filename"], f.get("status"), _change(f), f.get("previous_filename")) for f in files
                  if not (skip_records and f["filename"].startswith("records/")))
    return hashlib.sha256(json.dumps([base_ref, rows]).encode()).hexdigest()


def _change(f: dict) -> str | None:
    """What the pull request itself changes in one file: the hash of its added and removed lines. A file that main
    also changed (elsewhere) after the tick then keeps the same fingerprint when the branch is brought up to date;
    any change to the pull request's own lines still voids it. Without a text diff (binary or very large files)
    the whole file's content hash is used, as before."""
    patch = f.get("patch")
    if patch is None:
        return f.get("sha")
    lines = [ln for ln in patch.split("\n") if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
    return "patch:" + hashlib.sha256("\n".join(lines).encode()).hexdigest()


def body_hash(body: str | None) -> str:
    """Hash of a review pull request's text with the Ship it box itself left out: it pins the owner's ticks."""
    text = (body or "").replace("\r\n", "\n")
    text = BOX.sub(SHIP_LINE, text).strip()
    return hashlib.sha256(text.encode()).hexdigest()


def decide(pr: dict, *, default_branch: str, bot: str, approved: str | None, current: str | None, behind_by: int,
           touches_workflows: bool, tests: str | None, review: dict | None = None) -> tuple[str, str]:
    """Next step for one pull request whose box is ticked: (action, detail).
    Actions: skip, note (detail = note key), wait, update, merge.
    review (review pull requests only): {"body_ok": bool, "sync_running": bool, "records_ok": bool | None}."""
    head = pr["head"]["sha"][:12]
    if pr.get("draft") or pr["head"]["repo"] is None or pr["head"]["repo"]["full_name"] != pr["base"]["repo"]["full_name"]:
        return "skip", "draft or from another repository"
    if is_review_pr(pr, bot) and review is None:
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
    if review is not None:
        if not review["body_ok"]:
            return "note", f"void-{head}"
        if review["sync_running"]:
            return "wait", "review sync running"
    if behind_by > 0:
        return "update", pr["head"]["sha"]
    if review is not None and not review["records_ok"]:
        return "note", f"records-{head}"
    if pr.get("mergeable_state") == "dirty" or pr.get("mergeable") is False:
        return "note", f"conflict-{head}"
    if tests is None or tests == "pending":
        return "wait", "tests running"
    if tests != "success":
        return "note", f"failed-{head}"
    return "merge", pr["head"]["sha"]


NOTES = {
    "review": "Ship it could not check this review pull request. Please merge it yourself.",
    "records": "The record changes on this branch do not match the ticked items (main may have changed since). Edit "
               "any tick (or untick and tick one) so the review sync rebuilds them; Ship it then carries on.",
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


def tick_change(event: dict, owner: str) -> tuple | None:
    """(pull request number, kind, head commit at that moment, text, text before) for an owner's edit: kind "tick" or
    "untick" when it flips the box, "edit" when the box stays ticked (review pull requests use it to follow the ticks)."""
    if event.get("action") != "edited" or (event.get("sender") or {}).get("login") != owner:
        return None
    before = ((event.get("changes") or {}).get("body") or {}).get("from")
    if before is None:
        return None
    pr = event["pull_request"]
    was, now = ticked(before), ticked(pr.get("body"))
    if was == now:
        return (pr["number"], "edit", pr["head"]["sha"], pr.get("body"), before) if now else None
    return pr["number"], ("tick" if now else "untick"), pr["head"]["sha"], pr.get("body"), before


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


def approval_state(comments: list[dict], review: bool | None = None) -> tuple[dict | None, str | None, str | None]:
    """(the approval comment, the approved fingerprint, the approved ticks hash); None when never approved, revoked,
    or approved in the other mode (a renamed title must never switch a review into an ordinary merge, or back)."""
    mine = [c for c in comments if APPROVED.search(c["body"] or "") or REVOKED in (c["body"] or "")]
    if not mine:
        return None, None, None
    last = mine[-1]
    m = APPROVED.search(last["body"] or "")
    if not m:
        return last, None, None
    mode = m.group(4) or ("review" if m.group(3) else "code")
    if review is not None and mode != ("review" if review else "code"):
        return last, None, None
    return last, m.group(1), m.group(3)


def approval_text(fp: str, head: str, body: str | None) -> str:
    extra = f" body={body} mode=review" if body else " mode=code"
    return (f"<!-- ship-it approved={fp} head={head}{extra} -->\nShip it: approved version `{head[:7]}`. It will be "
            "brought up to date, tested and merged without further clicks.")


SAFE_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_TERMINAL_PROMPT": "0"}


def _env() -> dict:
    """A minimal environment for work on the pull request's files: no keys, no git settings, no hooks."""
    keep = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ}
    return {**keep, **SAFE_ENV}


def recompute_records(work: str, main_dir: str, n: int, body: str, base: str, today: str | None = None) -> bool:
    """In the scratch copy `work`, rebuild records/ from the ticks in `body` with main's own code and settings (the
    copy's code is never imported: python -I, main's folder first on the path) and report whether the copy's records/
    are exactly that: nothing changed, removed or added."""
    for top in ("records", "reports"):
        for dirpath, dirs, files in os.walk(os.path.join(work, top)):
            if any(os.path.islink(os.path.join(dirpath, x)) for x in dirs + files):
                return False                                  # links could point outside the copy
    body_file = os.path.join(tempfile.mkdtemp(dir=os.environ.get("RUNNER_TEMP")), "body.md")
    with open(body_file, "w", encoding="utf-8") as f:
        f.write(body)
    code = "import sys; sys.path.insert(0, sys.argv[1]); from kgkit import review; sys.exit(review.main(sys.argv[2:]))"
    args = ["python3", "-I", "-c", code, main_dir, "sync", "--config", os.path.join(main_dir, "kit.tinnitus.yaml"),
            "--records", "records/tinnitus.records.json", "--pr", str(n), "--body-file", body_file,
            "--proposals", "reports/proposals.json", "--base", base, *(["--today", today] if today else [])]
    try:
        r = subprocess.run(args, cwd=work, capture_output=True, text=True, env=_env(), timeout=300)
    except subprocess.TimeoutExpired:
        return False
    finally:
        os.remove(body_file)
    if r.returncode != 0:
        return False
    def status(*extra: str) -> str:
        return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", work, "status", "--porcelain",
                               "--untracked-files=all", *extra], capture_output=True, text=True, check=True,
                              env=_env()).stdout
    # The whole copy must be unchanged, and inside records/ even files a .gitignore would hide must match.
    diff = status() + status("--ignored=matching", "--", "records")
    return diff.strip() == ""


SYNC_DATE = re.compile(r"^Ticked items ready to go live with the merge \(([0-9]{4}-[0-9]{2}-[0-9]{2})\)")


def sync_date(message: str) -> str | None:
    """The date the review sync recorded, accepted only if it is a real date within the last two weeks."""
    import datetime as dt
    m = SYNC_DATE.match(message or "")
    if not m:
        return None
    try:
        day = dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None
    today = dt.datetime.now(dt.timezone.utc).date()
    return m.group(1) if today - dt.timedelta(days=14) <= day <= today else None


def records_match(n: int, head_sha: str, body: str, default_branch: str) -> bool:
    """Fetch the pull request into a scratch copy (as data) and check its records/ follow from the ticks, using the
    date the review sync recorded so dates match exactly."""
    main_dir = os.getcwd()
    work = tempfile.mkdtemp(prefix=f"shipit-{n}-", dir=os.environ.get("RUNNER_TEMP"))
    git = ["git", "-c", "core.hooksPath=/dev/null", "-C", main_dir]
    try:
        subprocess.run(git + ["fetch", "-q", "--no-tags", "origin", f"+refs/pull/{n}/head:refs/shipit/pr-{n}",
                              f"+refs/heads/{default_branch}:refs/remotes/origin/{default_branch}"],
                       check=True, capture_output=True, env=_env(), timeout=120)
        msg = subprocess.run(git + ["log", "-1", "--format=%s", head_sha], capture_output=True, text=True,
                             env=_env()).stdout.strip()
        day = sync_date(msg)
        subprocess.run(git + ["worktree", "add", "-q", "--detach", work, head_sha], check=True, capture_output=True,
                       env=_env(), timeout=120)
        return recompute_records(work, main_dir, n, body, f"origin/{default_branch}", day)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    finally:
        subprocess.run(git + ["worktree", "remove", "--force", work], capture_output=True, env=_env())


def _recent(stamp: str | None, minutes: int = 5) -> bool:
    import datetime as dt
    try:
        when = dt.datetime.fromisoformat((stamp or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    return dt.datetime.now(dt.timezone.utc) - when < dt.timedelta(minutes=minutes)


def ship_one(gh: Repo, n: int, default_branch: str, bot: str, change: tuple | None, summary: list,
             check_records=records_match) -> None:
    pr = call("GET", f"/repos/{gh.repo}/pulls/{n}", gh.read)
    review = is_review_pr(pr, bot)
    comments = gh.app_comments(n)
    approval_c, approved, approved_body = approval_state(comments, review)
    if change and change[0] == n:
        kind, sha, text, before = change[1], change[2], change[3], (change[4] if len(change) > 4 else None)
        if kind == "untick":
            # Always written, even when no approval exists yet: a tick run that finishes later sees it and stops.
            gh.comment(n, f"{REVOKED}\nShip it: approval withdrawn.", approval_c)
            summary.append(f"#{n}: approval withdrawn")
            return
        if kind == "tick":
            fp = fingerprint(pr["base"]["ref"], gh.compare(default_branch, sha), skip_records=review)
            latest = approval_state(gh.app_comments(n))[0]
            if latest is not None and REVOKED in (latest.get("body") or "") and \
                    (latest.get("updated_at") or latest.get("created_at") or "") > (pr.get("updated_at") or ""):
                fp = None                     # unticked again after this tick: never approve
            if not ticked(call("GET", f"/repos/{gh.repo}/pulls/{n}", gh.read).get("body")):
                fp = None                     # the box is no longer ticked
            if fp:
                approved, approved_body = fp, (body_hash(text) if review else None)
                gh.comment(n, approval_text(fp, sha, approved_body), approval_c)
                summary.append(f"#{n}: approved")
        elif kind == "edit" and review and approved and approved_body and before is not None \
                and body_hash(before) == approved_body:
            # The owner changed ticks after Ship it, starting from the approved text: follow the new ticks, keep the
            # approved content. An edit that starts from text someone else changed keeps the approval void.
            m = APPROVED.search(approval_c["body"])
            approved_body = body_hash(text)
            gh.comment(n, approval_text(approved, m.group(2), approved_body), approval_c)
            summary.append(f"#{n}: ticks updated")
        if review:
            return      # the review sync started by this same edit triggers the next check when it finishes
    if not ticked(pr.get("body")):
        return
    noted = {m.group(1) for c in comments for m in NOTE.finditer(c["body"] or "")}
    cur = gh.compare(default_branch, pr["head"]["sha"])
    current = fingerprint(pr["base"]["ref"], cur, skip_records=review)
    touches_wf = any(f["filename"].startswith(".github/") for f in cur.get("files") or [])
    outside = review and any(not f["filename"].startswith(("reports/", "records/")) or
                             (f.get("previous_filename") or "reports/").split("/")[0] not in ("reports", "records") or
                             os.path.basename(f["filename"]) in (".gitignore", ".gitattributes", ".gitmodules")
                             for f in cur.get("files") or [])
    tests = tests_result(gh.repo, pr["head"]["sha"], gh.read)
    review_state = None
    if outside:
        touches_wf = False
        review_state = None
    elif review:
        sync = [r for s in ("queued", "in_progress") for r in call(
            "GET", f"/repos/{gh.repo}/actions/workflows/review-sync.yml/runs?status={s}&per_page=50", gh.read)
            .get("workflow_runs", [])]   # any running sync: its runs report main as their branch
        body_ok = bool(approved_body) and approved_body == body_hash(pr.get("body"))
        ready = body_ok and not sync and current == approved and approved is not None
        review_state = {"body_ok": body_ok, "sync_running": bool(sync),
                        "records_ok": check_records(n, pr["head"]["sha"], pr.get("body") or "", default_branch)
                        if ready else None}
    behind = int(cur.get("behind_by") or 0)
    main_sha = None
    if behind:
        # Main moved on. If nothing main changed touches this pull request's files, merge as it is: bringing it up to
        # date would need the app to rewrite automation files main changed, a power it deliberately lacks.
        since = call("GET", f"/repos/{gh.repo}/compare/{pr['head']['sha']}...{default_branch}?per_page=100", gh.read)
        theirs = {f["filename"] for f in since.get("files") or []}
        ours = {f["filename"] for f in cur.get("files") or []}
        if since.get("files") is not None and len(since["files"]) < MAX_FILES and not (theirs & ours):
            behind = 0
            main_sha = (since.get("commits") or [{}])[-1].get("sha")
    action, detail = decide(pr, default_branch=default_branch, bot=bot, approved=approved, current=current,
                            behind_by=behind, touches_workflows=touches_wf, tests=tests, review=review_state)
    if action == "note" and detail.startswith("unapproved") and change is None and _recent(pr.get("updated_at")):
        action, detail = "wait", "the owner's tick may still be on its way"   # no false alarm right after a tick
    if action == "merge" and review:
        fresh = call("GET", f"/repos/{gh.repo}/pulls/{n}", gh.read)       # ticks must not have changed meanwhile
        again = gh.compare(default_branch, detail)                         # nor main
        moved = int(again.get("behind_by") or 0) > 0 and \
            call("GET", f"/repos/{gh.repo}/branches/{default_branch}", gh.read).get("commit", {}).get("sha") != main_sha
        if fresh["head"]["sha"] != detail or body_hash(fresh.get("body")) != approved_body or \
                not ticked(fresh.get("body")) or moved:
            action, detail = "wait", "changed while checking"
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
        if review:
            summary.append(f"#{n}: merged review")


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
        if any(x.endswith(": merged review") for x in summary):
            break                              # one review per run: the next run sees main as it is now
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
