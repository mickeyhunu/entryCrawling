"""gangnambside.com 피드를 주기적으로 확인해서 새 엔트리 글을 MySQL 에 넣는다.

동작:
    1. INTERVAL 초마다 피드를 크롤링한다.
    2. 20시간 이내 '엔트리' 글 중 아직 처리하지 않은 글을 찾는다.
    3. 그 글의 명단을 ENTRY_TODAY / ENTRY_ALLDAY 에 넣는다 (entry_db.save_entries).
    4. 처리한 글은 seen_posts.json 에 기록해서, 재시작해도 다시 넣지 않는다.

사용 예:
    python entry_watcher.py                    # 60초마다 확인 (Ctrl+C 로 종료)
    python entry_watcher.py --interval 300     # 5분마다 확인
    python entry_watcher.py --once             # 한 번만 확인하고 종료 (작업 스케줄러용)
    python entry_watcher.py --skip-existing    # 지금 피드에 있는 글은 넣지 않고 기록만
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from entry_crawler import (
    FEED_URL,
    MAX_AGE_HOURS,
    EntryPost,
    fetch_feed_html,
    is_recent,
    parse_feed_html,
    rows_for_post,
)

STATE_FILE = Path(__file__).with_name("seen_posts.json")
STATE_KEEP_DAYS = 3  # 이보다 오래된 기록은 지운다 (20시간 지난 글은 어차피 대상이 아님)

log = logging.getLogger("entry_watcher")


def load_state(path: Path) -> dict[str, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save_state(path: Path, state: dict[str, str]) -> None:
    cutoff = (datetime.now() - timedelta(days=STATE_KEEP_DAYS)).isoformat()
    for key in [k for k, seen_at in state.items() if seen_at < cutoff]:
        del state[key]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def find_new_posts(
    posts: list[EntryPost], seen: dict[str, str], max_hours: float = MAX_AGE_HOURS
) -> list[EntryPost]:
    """아직 처리하지 않은 오늘 엔트리 글을 오래된 순으로 돌려준다."""
    new: dict[str, EntryPost] = {}
    for post in posts:
        if post.is_entry and is_recent(post.time_text, max_hours) and post.key not in seen:
            new.setdefault(post.key, post)
    return list(reversed(new.values()))  # 피드는 최신순


def run_once(
    fetch: Callable[[], str],
    save: Callable[[list[dict]], int],
    state: dict[str, str],
    state_path: Path,
    max_hours: float = MAX_AGE_HOURS,
    skip: bool = False,
) -> int:
    """피드를 한 번 확인해 새 글을 저장하고, 저장한 행 수를 돌려준다."""
    posts = parse_feed_html(fetch())
    saved = 0
    for post in find_new_posts(posts, state, max_hours):
        rows = rows_for_post(post)
        if rows is None:
            # storeNo 를 추가한 뒤 재시작하면 넣을 수 있도록 기록하지 않는다
            continue
        if skip:
            log.info("건너뜀(기존 글): %s %s", post.shop_name, post.time_text)
        elif not rows:
            log.warning("명단을 찾지 못함: %s %s", post.shop_name, post.time_text)
        else:
            saved += save(rows)
            log.info("저장: %s(%s) %d명 [%s]",
                     post.shop_name, rows[0]["storeNo"], len(rows), post.time_text)
        # 글마다 DB 커밋 직후 기록해서, 중간에 멈춰도 같은 글을 두 번 넣지 않는다
        state[post.key] = datetime.now().isoformat(timespec="seconds")
        save_state(state_path, state)
    return saved


def install_stop_handlers() -> threading.Event:
    """Ctrl+C, 콘솔 창 닫기, 서비스 중지 신호를 받으면 stop 이벤트만 켠다.

    크롤링 도중에 예외로 끊으면 Playwright 가 정리되지 않고 멈출 수 있어서,
    진행 중인 확인은 끝까지 마치고(브라우저·DB 연결 정상 종료) 루프를 빠져나온다.
    두 번째 신호는 즉시 강제 종료한다.
    """
    stop = threading.Event()

    def handler(signum, frame):
        if stop.is_set():
            log.warning("강제 종료")
            os._exit(1)
        log.info("종료 요청 받음: 진행 중인 확인을 마치고 종료합니다 (한 번 더 누르면 강제 종료)")
        stop.set()

    # SIGBREAK: Windows 콘솔 창 닫기 / Ctrl+Break
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), handler)
    return stop


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="새 엔트리 글을 감시해서 DB 에 저장")
    ap.add_argument("--url", default=FEED_URL, help="피드 URL (기본: %(default)s)")
    ap.add_argument("--interval", type=int, default=600, help="확인 주기(초) (기본: %(default)s)")
    ap.add_argument("--max-hours", type=float, default=MAX_AGE_HOURS,
                    help="이 시간 이내 글만 대상 (기본: %(default)s)")
    ap.add_argument("--once", action="store_true", help="한 번만 확인하고 종료")
    ap.add_argument("--skip-existing", action="store_true",
                    help="첫 확인 때 이미 올라와 있는 글은 DB 에 넣지 않고 처리한 것으로 기록")
    ap.add_argument("--state", type=Path, default=STATE_FILE, help="처리 기록 파일")
    ap.add_argument("--headful", action="store_true", help="브라우저 창을 띄워서 실행")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")

    from entry_db import load_db_config, save_entries

    load_db_config()  # 접속 정보가 없으면 시작할 때 바로 알린다
    stop = install_stop_handlers()

    def fetch() -> str:
        return fetch_feed_html(args.url, max_hours=args.max_hours, headless=not args.headful)

    state = load_state(args.state)
    skip = args.skip_existing
    log.info("감시 시작: %s (%d초 간격)", args.url, args.interval)
    while not stop.is_set():
        try:
            saved = run_once(fetch, save_entries, state, args.state, args.max_hours, skip)
            skip = False
            log.info("확인 완료: 새로 저장 %d행", saved)
        except Exception:
            # 네트워크/DB 일시 오류는 기록만 하고 다음 주기에 다시 시도
            log.exception("확인 중 오류")
        if args.once:
            break
        stop.wait(args.interval)  # 대기 중 종료 신호가 오면 바로 깨어난다
    log.info("감시 종료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
