"""Local web dashboard: serves the HTML page and a JSON usage endpoint."""

from __future__ import annotations

import json
import time
import urllib.error
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from devin_usage.core import Session, bucketize, to_json

INDEX_HTML = (Path(__file__).parent / "static" / "index.html").read_bytes()
CACHE_SECONDS = 60
MAX_WINDOWS = 30
MAX_HOURS = 24

Loader = Callable[[int], list[Session]]


def make_handler(load: Loader, clock: Callable[[], float] = time.time) -> type[BaseHTTPRequestHandler]:
    cache: dict[int, tuple[float, list[Session]]] = {}

    def cached_load(created_after: int, now: float) -> list[Session]:
        key = created_after // CACHE_SECONDS
        hit = cache.get(key)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
        sessions = load(created_after)
        cache.clear()
        cache[key] = (now, sessions)
        return sessions

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path == "/":
                self.send(HTTPStatus.OK, INDEX_HTML, "text/html; charset=utf-8")
            elif url.path == "/api/usage":
                self.usage(parse_qs(url.query))
            else:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def usage(self, query: dict[str, list[str]]) -> None:
            try:
                windows = int(query.get("windows", ["3"])[0])
                hours = int(query.get("hours", ["5"])[0])
            except ValueError:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "windows と hours は整数で指定してください"})
                return
            if not (1 <= windows <= MAX_WINDOWS and 1 <= hours <= MAX_HOURS):
                self.send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": f"windows は1〜{MAX_WINDOWS}、hours は1〜{MAX_HOURS}で指定してください"},
                )
                return
            now = int(clock())
            try:
                sessions = cached_load(now - windows * hours * 3600, now)
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                self.send_json(HTTPStatus.BAD_GATEWAY, {"error": f"Devin API error {e.code}: {detail}"})
                return
            except urllib.error.URLError as e:
                self.send_json(HTTPStatus.BAD_GATEWAY, {"error": f"Devin API に接続できません: {e.reason}"})
                return
            self.send_json(HTTPStatus.OK, to_json(bucketize(sessions, now, hours, windows), now, hours))

        def send_json(self, status: HTTPStatus, body: dict) -> None:
            self.send(status, json.dumps(body, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return Handler


def serve(load: Loader, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(load))
    print(f"Devin利用量ダッシュボード: http://{host}:{server.server_port}/  (Ctrl+C で終了)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
