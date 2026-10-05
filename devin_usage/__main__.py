"""Command line entry point: `report` prints a table, `serve` starts the web dashboard."""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
from datetime import datetime, timezone

from devin_usage.core import Session, bucketize, demo_sessions, fetch_sessions, http_fetch
from devin_usage.server import Loader, serve


def make_loader(demo: bool) -> Loader:
    if demo:
        now = int(time.time())
        sessions = demo_sessions(now, hours=24, windows=3)
        return lambda created_after: [s for s in sessions if s.created_at >= created_after]
    token, org = os.environ.get("DEVIN_PAT"), os.environ.get("DEVIN_ORG_ID")
    if not token or not org:
        sys.exit("環境変数 DEVIN_PAT と DEVIN_ORG_ID を設定してください（お試しは --demo）")
    fetch = http_fetch(token)
    return lambda created_after: fetch_sessions(fetch, org, created_after)


def report(load: Loader, windows: int, hours: int) -> None:
    now = int(time.time())
    try:
        sessions: list[Session] = load(now - windows * hours * 3600)
    except urllib.error.HTTPError as e:
        sys.exit(f"Devin API error {e.code}: {e.read().decode(errors='replace')[:300]}")
    fmt = "%m/%d %H:%M"

    def local(t: int) -> str:
        return datetime.fromtimestamp(t, timezone.utc).astimezone().strftime(fmt)

    print(f"{'期間':<25}{'セッション数':>8}{'ACU':>10}")
    buckets = bucketize(sessions, now, hours, windows)
    for w in buckets:
        label = f"{local(w.start)} - {local(w.end)}"
        print(f"{label:<25}{len(w.sessions):>8}{w.acus:>12.2f}")
    total = sum(w.acus for w in buckets)
    print(f"{'合計':<25}{sum(len(w.sessions) for w in buckets):>8}{total:>12.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="devin-usage", description="Devinの利用量（ACU）を時間帯ごとに集計します")
    parser.add_argument("--demo", action="store_true", help="APIを使わずダミーデータで動かす")
    parser.set_defaults(windows=3, hours=5)
    sub = parser.add_subparsers(dest="command")
    rep = sub.add_parser("report", help="ターミナルに表で表示（既定）")
    rep.add_argument("windows", nargs="?", type=int, default=3)
    rep.add_argument("hours", nargs="?", type=int, default=5)
    srv = sub.add_parser("serve", help="Webダッシュボードを起動")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    load = make_loader(args.demo)
    if args.command == "serve":
        serve(load, args.host, args.port)
    else:
        report(load, args.windows, args.hours)


if __name__ == "__main__":
    main()
