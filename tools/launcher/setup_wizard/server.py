"""Setup wizard: a small local web page that walks through the setup with Connect / Create / Install buttons.

Run:  python3 -m tools.launcher.setup_wizard.server --repo OWNER/REPO   (then open the address it prints)
Listens on 127.0.0.1 only. Every API call needs the per-launch token embedded in the page; GitHub's returns are
checked against a per-launch state value. The setup key and the app's private key stay in this process's memory and
are dropped when setup finishes; neither is written to disk or to the log.
"""
from __future__ import annotations

import argparse
import html
import json
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional

from . import engine

VERSION = "0.1.0"
UI = Path(__file__).with_name("ui.html")


class State:
    def __init__(self, repo: str, app_name: str, port: int, api=engine.real_api):
        self.repo, self.app_name, self.port, self.api = repo, app_name, port, api
        self.launch = secrets.token_urlsafe(24)       # guards this page's own API
        self.state = engine.new_state()               # guards GitHub's returns
        self.setup_key: Optional[str] = None
        self.login: Optional[str] = None
        self.app: Optional[dict] = None               # id, slug, pem (memory only), html_url
        self.installation_id: Optional[str] = None
        self.results: List[dict] = []
        self.log: List[str] = []
        self.busy = False
        self.lock = threading.Lock()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def status(self) -> dict:
        return {"repo": self.repo, "version": VERSION, "connected": bool(self.setup_key), "login": self.login,
                "key_url": engine.setup_key_url(self.repo.split("/")[0]),
                "app": {k: v for k, v in (self.app or {}).items() if k != "pem"} or None,
                "install_url": engine.install_url(self.app["slug"]) if self.app else None,
                "installed": bool(self.installation_id), "busy": self.busy, "results": self.results,
                "done": bool(self.results) and all(r["ok"] for r in self.results), "log": self.log[-20:]}

    def note(self, line: str) -> None:
        self.log.append(line)


def make_handler(st: State):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):            # the default log prints full URLs (codes): never
            pass

        def _send(self, code: int, body: str, kind: str = "application/json") -> None:
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", f"{kind}; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _page(self, title: str, text: str) -> None:
            self._send(200, f"<!doctype html><meta charset='utf-8'><title>{html.escape(title)}</title>"
                            f"<p>{html.escape(text)}</p><p><a href='/'>Back to the setup page</a></p>"
                            "<script>setTimeout(()=>location='/',1500)</script>", "text/html")

        def do_GET(self):
            try:
                if not self._host_ok():
                    return self._send(403, json.dumps({"error": "wrong host"}))
                url = urllib.parse.urlparse(self.path)
                q = dict(urllib.parse.parse_qsl(url.query))
                if url.path == "/":
                    return self._send(200, UI.read_text(encoding="utf-8").replace("__LAUNCH__", st.launch),
                                      "text/html")
                if url.path == "/ping":
                    return self._send(200, f"setup-wizard {VERSION}", "text/plain")
                if url.path == "/api/status" and q.get("t") == st.launch:
                    return self._send(200, json.dumps(st.status()))
                if url.path == "/create" and q.get("t") == st.launch:
                    owner = st.repo.split("/")[0]
                    return self._send(200, engine.create_app_form(owner, st.app_name, st.repo, st.base_url, st.state),
                                      "text/html")
                if url.path == "/created":
                    if q.get("state") != st.state:
                        return self._page("Not accepted", "This return from GitHub does not belong to this setup.")
                    with st.lock:
                        st.app = engine.convert(st.api, q.get("code", ""))
                    st.note(f"App created: {st.app['slug']}")
                    return self._page("App created", "The app is created. Next: install it.")
                if url.path == "/installed":
                    # GitHub sends installation_id here after Install; the app's own key confirms it in step 4.
                    st.installation_id = q.get("installation_id") if (q.get("installation_id") or "").isdigit() else None
                    st.note("App installed" if st.installation_id else "Install return without an installation id")
                    return self._page("Installed", "Installed. Finishing the setup on the setup page.")
                return self._send(404, json.dumps({"error": "not found"}))
            except engine.SetupError as e:
                st.note(str(e))
                return self._page("Problem", str(e))
            except Exception as e:  # noqa: BLE001 - always answer
                return self._send(500, json.dumps({"error": type(e).__name__}))

        def do_POST(self):
            try:
                if not self._host_ok():
                    return self._send(403, json.dumps({"error": "wrong host"}))
                url = urllib.parse.urlparse(self.path)
                if dict(urllib.parse.parse_qsl(url.query)).get("t") != st.launch:
                    return self._send(403, json.dumps({"error": "not this page"}))
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                if url.path == "/api/connect":
                    key = (body.get("key") or "").strip()
                    info = engine.check_setup_key(st.api, st.repo, key)
                    st.setup_key, st.login = key, info["login"]
                    st.note(f"Connected as {st.login}")
                    return self._send(200, json.dumps(st.status()))
                if url.path == "/api/finish":
                    if not (st.setup_key and st.app):
                        raise engine.SetupError("Connect GitHub and create the app first.")
                    with st.lock:
                        if st.busy:
                            raise engine.SetupError("Already running.")
                        st.busy = True
                    try:
                        st.results = engine.finish(st.api, st.repo, st.setup_key, st.app, st.installation_id,
                                                   log=st.note)
                    finally:
                        st.busy = False
                    if all(r["ok"] for r in st.results):
                        st.app.pop("pem", None)            # done: drop the private key from memory
                        st.setup_key = None                 # and the setup key
                        st.note("Setup finished; keys dropped from memory")
                    return self._send(200, json.dumps(st.status()))
                return self._send(404, json.dumps({"error": "not found"}))
            except engine.SetupError as e:
                st.note(str(e))
                return self._send(400, json.dumps({"error": str(e)}))
            except Exception as e:  # noqa: BLE001
                return self._send(500, json.dumps({"error": type(e).__name__}))
    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Set up the Ship it app for a repository")
    ap.add_argument("--repo", required=True, help="OWNER/REPO")
    ap.add_argument("--app-name", default=None, help="name for the new app (default: <repo>-ship-it)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    if args.repo.count("/") != 1:
        raise SystemExit("--repo must look like OWNER/REPO")
    st = State(args.repo, args.app_name or f"{args.repo.split('/')[1]}-ship-it", args.port)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(st))
    print(f"Setup page: {st.base_url}/")
    if not args.no_browser:
        webbrowser.open(f"{st.base_url}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
