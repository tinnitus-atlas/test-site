"""Acceptance test for WP-A8: every GitHub Action is pinned to a full commit SHA, and the Hermes job text names no
real home folder."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_action_pinned_by_commit_sha():
    bad = []
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for ref in re.findall(r"uses:\s*([^\s#]+)", wf.read_text()):
            if not ref.startswith("./") and not re.search(r"@[0-9a-f]{40}$", ref):
                bad.append("%s: %s" % (wf.name, ref))
    assert not bad, bad


def test_hermes_job_names_no_home_folder():
    assert not re.search(r"/home/(?!<)[a-z]", (ROOT / "hermes" / "nightly-job.md").read_text())
