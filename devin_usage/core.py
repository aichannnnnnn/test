"""Fetch Devin sessions and aggregate their ACU usage into fixed-length time windows."""

from __future__ import annotations

import json
import random
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass

API_URL = "https://api.devin.ai/v3/organizations/{org}/sessions"
PAGE_SIZE = 200

Fetch = Callable[[str], dict]


@dataclass(frozen=True)
class Session:
    session_id: str
    title: str
    created_at: int
    acus: float
    status: str
    url: str


@dataclass(frozen=True)
class Window:
    start: int
    end: int
    sessions: tuple[Session, ...]

    @property
    def acus(self) -> float:
        return sum(s.acus for s in self.sessions)


def http_fetch(token: str) -> Fetch:
    def fetch(url: str) -> dict:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.load(res)

    return fetch


def parse_session(item: dict) -> Session:
    return Session(
        session_id=item["session_id"],
        title=item.get("title") or "(無題)",
        created_at=int(item["created_at"]),
        acus=float(item.get("acus_consumed") or 0.0),
        status=item.get("status") or "",
        url=item.get("url") or "",
    )


def fetch_sessions(fetch: Fetch, org: str, created_after: int) -> list[Session]:
    sessions: list[Session] = []
    cursor: str | None = None
    while True:
        params: dict[str, str | int] = {"first": PAGE_SIZE, "created_after": created_after}
        if cursor:
            params["after"] = cursor
        page = fetch(API_URL.format(org=org) + "?" + urllib.parse.urlencode(params))
        sessions.extend(parse_session(item) for item in page["items"])
        cursor = page.get("end_cursor")
        if not page.get("has_next_page") or not cursor:
            return sessions


def bucketize(sessions: Iterable[Session], now: int, hours: int, windows: int) -> list[Window]:
    """Group sessions by creation time into `windows` spans of `hours`, newest first."""
    span = hours * 3600
    ordered = sorted(sessions, key=lambda s: s.created_at, reverse=True)
    result = []
    for i in range(windows):
        end, start = now - i * span, now - (i + 1) * span
        result.append(Window(start, end, tuple(s for s in ordered if start <= s.created_at < end)))
    return result


def to_json(windows: list[Window], now: int, hours: int) -> dict:
    return {
        "generated_at": now,
        "hours": hours,
        "total_acus": round(sum(w.acus for w in windows), 2),
        "total_sessions": sum(len(w.sessions) for w in windows),
        "windows": [
            {
                "start": w.start,
                "end": w.end,
                "acus": round(w.acus, 2),
                "sessions": [
                    {
                        "session_id": s.session_id,
                        "title": s.title,
                        "created_at": s.created_at,
                        "acus": round(s.acus, 2),
                        "status": s.status,
                        "url": s.url,
                    }
                    for s in w.sessions
                ],
            }
            for w in windows
        ],
    }


def demo_sessions(now: int, hours: int, windows: int, seed: int = 1) -> list[Session]:
    rng = random.Random(seed)
    span = hours * windows * 3600
    titles = ["READMEをUTF-8に修正", "CSV集計CLIを追加", "テストを追加", "利用量ダッシュボード", "バグ調査"]
    return [
        Session(
            session_id=f"demo-{i}",
            title=rng.choice(titles),
            created_at=now - rng.randrange(span),
            acus=round(rng.uniform(0.2, 4.0), 2),
            status=rng.choice(["running", "exit", "suspended"]),
            url="",
        )
        for i in range(rng.randrange(hours * windows // 3, hours * windows // 2))
    ]
