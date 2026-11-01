"""Shared plumbing: configuration, records, HTTP with cache and backoff, text helpers, report writing."""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

import yaml

USER_AGENT = "kg-quality-kit/0.1 (+https://github.com/; open knowledge graph quality checks)"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class KitError(Exception):
    """Bad configuration or records. Exit code 2."""


class FetchError(Exception):
    """A remote service could not be reached or returned an error."""


# ---------------------------------------------------------------------------
# Configuration and records
# ---------------------------------------------------------------------------

def load_config(path: str | Path) -> dict:
    try:
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise KitError(f"Configuration not found: {path}") from exc
    for key in ("project", "kinds", "predicates"):
        if key not in cfg:
            raise KitError(f"Configuration is missing the '{key}' section")
    return cfg


def load_records(path: str | Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KitError(f"Records file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise KitError(f"Records file is not valid JSON: {exc}") from exc
    records = data.get("records") if isinstance(data, dict) else data
    if not isinstance(records, list):
        raise KitError("Records file must be a list or an object with a 'records' list")
    return records


def today() -> dt.date:
    return dt.date.today()


def parse_date(value) -> dt.date | None:
    """Accept YYYY-MM-DD or YYYY-MM (registries often give month precision)."""
    if not isinstance(value, str):
        return None
    try:
        if DATE.match(value):
            return dt.date.fromisoformat(value)
        if re.match(r"^\d{4}-\d{2}$", value):
            return dt.date.fromisoformat(value + "-01")
    except ValueError:
        return None
    return None


def fact_value(record: dict, key: str):
    fact = (record.get("facts") or {}).get(key)
    return fact.get("value") if isinstance(fact, dict) else fact


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

Fetcher = Callable[[str], dict]


class Http:
    """JSON GET with a polite pause, retries with backoff and an on-disk cache.

    Tests pass `fetcher` to replace the network with canned responses.
    """

    def __init__(self, cache_dir: str | Path | None = None, max_age_hours: float = 20,
                 pause: float = 0.35, retries: int = 3, fetcher: Fetcher | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_age = max_age_hours * 3600
        self.pause = pause
        self.retries = retries
        self.fetcher = fetcher
        self.calls = 0

    def get_json(self, url: str) -> dict:
        if self.fetcher:
            self.calls += 1
            return self.fetcher(url)
        cached = self._cache_path(url)
        if cached and cached.exists() and time.time() - cached.stat().st_mtime < self.max_age:
            return json.loads(cached.read_text(encoding="utf-8"))
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                time.sleep(self.pause)
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read().decode("utf-8"))
                self.calls += 1
                if cached:
                    cached.parent.mkdir(parents=True, exist_ok=True)
                    cached.write_text(json.dumps(data), encoding="utf-8")
                return data
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code == 404:
                    raise FetchError(f"404 for {url}") from exc
                if exc.code not in (429, 500, 502, 503, 504):
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                last = exc
            time.sleep(2 ** attempt)
        raise FetchError(f"Could not fetch {url}: {last}")

    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")


def qs(params: dict) -> str:
    return urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

STOP = set("""a an and or of the in for with without to on at by from as is are was were be been vs versus than
that this these those its it their there into onto over under after before during between among within via per
not no nor but if then so such can may might will would should could also more most less least other others
study studies trial trials patients patient people adults adult review systematic randomised randomized clinical
effect effects using use used based new""".split())


def normalise(text: str) -> str:
    """Lower-case, strip tags and entities, unify quotes and dashes, collapse whitespace."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[‐-―]", "-", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def tokens(text: str) -> set[str]:
    out = set()
    for raw in re.findall(r"[a-z0-9]+", normalise(text)):
        if raw in STOP:
            continue
        if raw.isdigit() or len(raw) >= 3:
            out.add(raw[:-1] if len(raw) > 4 and raw.endswith("s") and not raw.endswith("ss") else raw)
    return out


def overlap(a: set[str], b: set[str]) -> list[str]:
    """Shared tokens; words of eight or more letters also match on their first eight letters."""
    shared = set(a & b)
    long_b = {w[:8] for w in b if len(w) >= 8}
    shared |= {w for w in a if len(w) >= 8 and w[:8] in long_b}
    return sorted(shared)


def levenshtein(a: str, b: str, cap: int = 3) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def write_report(reports_dir: str | Path, name: str, payload: dict) -> Path:
    path = Path(reports_dir) / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **payload}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_report(reports_dir: str | Path, name: str) -> dict | None:
    path = Path(reports_dir) / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
