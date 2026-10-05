import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from email.message import Message
from http.server import ThreadingHTTPServer

import pytest

from devin_usage.core import Session
from devin_usage.server import make_handler

NOW = 1_800_000_000


def serve(load) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(load, clock=lambda: NOW))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def calls() -> list[int]:
    return []


@pytest.fixture
def base(calls) -> Iterator[str]:
    def load(created_after: int) -> list[Session]:
        calls.append(created_after)
        return [Session("s1", "テスト", NOW - 3600, 1.5, "exit", "https://app.devin.ai/sessions/s1")]

    yield from serve(load)


def get(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url) as res:
            return res.status, json.load(res)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_index_served(base):
    with urllib.request.urlopen(base + "/") as res:
        assert res.headers["Content-Type"].startswith("text/html")
        assert "Devin利用量ダッシュボード" in res.read().decode()


def test_usage_endpoint_and_cache(base, calls):
    status, body = get(base + "/api/usage?windows=2&hours=8")
    assert status == 200
    assert body["total_acus"] == 1.5
    assert body["windows"][0]["sessions"][0]["title"] == "テスト"
    assert calls == [NOW - 16 * 3600]

    get(base + "/api/usage?windows=2&hours=8")
    assert len(calls) == 1


@pytest.mark.parametrize("query", ["windows=abc", "windows=0", "hours=25"])
def test_usage_rejects_bad_params(base, query):
    status, body = get(base + "/api/usage?" + query)
    assert status == 400
    assert "error" in body


def test_api_error_is_reported():
    def load(created_after: int) -> list[Session]:
        raise urllib.error.HTTPError("https://api.devin.ai", 403, "Forbidden", Message(), None)

    for base in serve(load):
        status, body = get(base + "/api/usage")
        assert status == 502
        assert "403" in body["error"]


def test_usage_defaults_to_three_five_hour_windows(base, calls):
    status, body = get(base + "/api/usage")
    assert status == 200
    assert body["hours"] == 5
    assert [w["end"] - w["start"] for w in body["windows"]] == [5 * 3600] * 3
    assert calls == [NOW - 15 * 3600]
