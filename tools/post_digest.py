#!/usr/bin/env python3
"""
Build the nightly chat digest from reports/nightly.md and post it to a webhook.

The digest format is fixed by hermes/nightly-job.md. The webhook address is read only from the
NIGHTLY_WEBHOOK_URL environment variable; when it is unset the digest is printed and nothing is sent.
The script never fails the run: it always exits 0.

Usage: python3 tools/post_digest.py --report reports/nightly.md --log reports/nightly.log --exit-code N
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

WEBHOOK_ENV = "NIGHTLY_WEBHOOK_URL"
LIMIT = 1800
APPROVAL_INSTRUCTION = (
    "To approve, tick the Approved box under each proposal you accept in the pull request description, "
    "then merge. Unticked items are ignored. Tomorrow's run applies the ticked ones."
)
WARNING = "These records stay off the website until fixed."
COPY_PREFIXES = (
    "Status:",
    "Could not reach:",
    "Held back from publishing",
    "Approved proposals:",
    "Website:",
    "Freshness:",
    "Registry mismatches:",
    "Feeds:",
    "Biolink export:",
)
TOP_PROPOSALS = "Top proposals:"
PULL_REQUEST = "Pull request:"
_LAST_ERROR = ""


def _fit(lines: list[str]) -> str:
    text = "\n".join(lines)
    if len(text) <= LIMIT:
        return text
    lines = list(lines)
    while len("\n".join(lines)) > LIMIT:
        index = max(range(len(lines)), key=lambda i: len(lines[i]))
        if len(lines[index]) <= 1:
            break
        lines[index] = lines[index][: max(1, len(lines[index]) // 2)]
    text = "\n".join(lines)
    return text[:LIMIT] if len(text) > LIMIT else text


def _failure_reason(report: str | None) -> str | None:
    if report is None:
        return None
    lines = report.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "Status: RUN FAILED" and index + 1 < len(lines):
            return lines[index + 1]
    return None


def _failure_digest(report: str | None, log_tail: str) -> str:
    lines = ["**Knowledge graph nightly run FAILED**"]
    reason = _failure_reason(report)
    if reason:
        lines.append(reason)
    lines.append("```")
    lines.extend(log_tail.splitlines()[-15:])
    lines.append("```")
    return _fit(lines)


def _is_proposal(line: str) -> bool:
    return bool(line) and line[0].isdigit() and ". [" in line


def _normal_digest(report: str) -> str:
    source = report.splitlines()
    date = ""
    if source and source[0].startswith("Nightly run "):
        date = source[0][len("Nightly run "):].strip()
    lines = [f"**Knowledge graph nightly run, {date}**"]
    pull_request = None
    in_top = False
    proposals = 0
    for line in source[1:]:
        if in_top and line.strip() == "none":  # copied exactly, as the format in hermes/nightly-job.md asks
            lines.append(line.strip())
            continue
        if in_top and _is_proposal(line):
            if proposals < 10:
                lines.append(line)
                proposals += 1
            continue
        in_top = False
        if line.strip() == TOP_PROPOSALS:
            lines.append(TOP_PROPOSALS)
            in_top = True
        elif line.startswith(PULL_REQUEST):
            pull_request = line
        elif line.startswith(COPY_PREFIXES):
            lines.append(line)
            if line.startswith("Held back from publishing"):
                lines.append(WARNING)
    if pull_request is not None:
        lines.append(pull_request)
        lines.append(APPROVAL_INSTRUCTION)
    return _fit(lines)


def build_digest(report: str | None, exit_code: int, log_tail: str = "") -> str:
    if exit_code == 2 or report is None:
        return _failure_digest(report, log_tail)
    return _normal_digest(report)


def post(text: str, url: str, timeout: float = 15) -> bool:
    global _LAST_ERROR
    _LAST_ERROR = ""
    if not url.startswith("https://"):
        _LAST_ERROR = "address is not https"
        return False
    try:
        body = json.dumps({"content": text, "text": text}).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            response.read()
        return True
    except Exception as exc:
        _LAST_ERROR = type(exc).__name__
        return False


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post the nightly digest to a chat webhook")
    parser.add_argument("--report", default="reports/nightly.md")
    parser.add_argument("--log", default="reports/nightly.log")
    parser.add_argument("--exit-code", type=int, default=0)
    args = parser.parse_args(argv)

    log_tail = _read(args.log) or ""
    report = _read(args.report)
    digest = build_digest(report, args.exit_code, log_tail)
    print(digest)

    url = (os.environ.get(WEBHOOK_ENV) or "").strip()
    if not url:
        print("Digest: skipped (no webhook configured)")
        return 0
    if post(digest, url):
        print("Digest: posted")
    else:
        print(f"Digest: posting FAILED ({_LAST_ERROR or 'error'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
