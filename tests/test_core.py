from urllib.parse import parse_qs, urlparse

from devin_usage.core import Session, bucketize, fetch_sessions, parse_session, to_json

HOUR = 3600
NOW = 1_800_000_000


def session(sid: str, created_at: int, acus: float) -> Session:
    return Session(sid, sid, created_at, acus, "exit", "")


def test_bucketize_groups_by_creation_time_newest_first():
    sessions = [
        session("a", NOW - 1 * HOUR, 1.0),
        session("b", NOW - 7 * HOUR, 2.0),
        session("c", NOW - 9 * HOUR, 0.5),
        session("old", NOW - 30 * HOUR, 9.0),
    ]
    windows = bucketize(sessions, NOW, hours=8, windows=3)

    assert [(w.start, w.end) for w in windows] == [
        (NOW - 8 * HOUR, NOW),
        (NOW - 16 * HOUR, NOW - 8 * HOUR),
        (NOW - 24 * HOUR, NOW - 16 * HOUR),
    ]
    assert [[s.session_id for s in w.sessions] for w in windows] == [["a", "b"], ["c"], []]
    assert [w.acus for w in windows] == [3.0, 0.5, 0.0]


def test_bucketize_window_start_is_inclusive():
    windows = bucketize([session("edge", NOW - 8 * HOUR, 1.0)], NOW, hours=8, windows=2)
    assert [len(w.sessions) for w in windows] == [1, 0]


def test_parse_session_tolerates_missing_optional_fields():
    s = parse_session({"session_id": "x", "created_at": NOW, "acus_consumed": None, "title": None})
    assert s == Session("x", "(無題)", NOW, 0.0, "", "")


def test_fetch_sessions_follows_pagination():
    pages = [
        {
            "items": [{"session_id": "1", "created_at": NOW, "acus_consumed": 1}],
            "has_next_page": True,
            "end_cursor": "c1",
        },
        {
            "items": [{"session_id": "2", "created_at": NOW, "acus_consumed": 2}],
            "has_next_page": False,
            "end_cursor": "c2",
        },
    ]
    urls: list[str] = []

    def fake_fetch(url: str) -> dict:
        urls.append(url)
        return pages[len(urls) - 1]

    sessions = fetch_sessions(fake_fetch, "org-1", created_after=NOW - HOUR)

    assert [s.session_id for s in sessions] == ["1", "2"]
    assert urlparse(urls[0]).path == "/v3/organizations/org-1/sessions"
    first, second = (parse_qs(urlparse(u).query) for u in urls)
    assert first["created_after"] == [str(NOW - HOUR)] and "after" not in first
    assert second["after"] == ["c1"]


def test_to_json_totals():
    windows = bucketize([session("a", NOW - HOUR, 1.234), session("b", NOW - 9 * HOUR, 2.0)], NOW, 8, 2)
    body = to_json(windows, NOW, 8)
    assert body["total_acus"] == 3.23
    assert body["total_sessions"] == 2
    assert body["windows"][0]["sessions"][0]["session_id"] == "a"
