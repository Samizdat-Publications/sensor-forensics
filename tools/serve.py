"""Serve the static web app (app/) on 127.0.0.1 only.

Usage (from the repo root):
    .venv/Scripts/python tools/serve.py            # http://127.0.0.1:8765/
    .venv/Scripts/python tools/serve.py --port 9000

Static files only, no caching of JSON (so a rebuilt export shows on reload).
"""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json"}

    def end_headers(self):
        if self.path.split("?")[0].endswith((".json", ".js", ".css", ".html", "/")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):  # quiet: only errors
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)


class Server(http.server.ThreadingHTTPServer):
    request_queue_size = 128  # the default 5 drops connections when ES modules load in parallel
    daemon_threads = True


def make_server(port: int = 8765) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(Handler, directory=str(APP))
    return Server(("127.0.0.1", port), handler)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Serve app/ on 127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    srv = make_server(a.port)
    print(f"Serving {APP} at http://127.0.0.1:{a.port}/  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
