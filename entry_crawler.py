"""gangnambside.com/feed 엔트리 게시글 크롤러.

피드 페이지는 Next.js 로 클라이언트 렌더링되고 "더보기" 버튼으로 게시글을 추가로
불러오기 때문에, Playwright(헤드리스 Chromium)로 페이지를 열어 버튼을 눌러가며
HTML 을 확보한 뒤 BeautifulSoup 으로 <article> 카드를 파싱한다.

사용 예:
    python entry_crawler.py                       # 첫 화면만 수집, JSON 출력
    python entry_crawler.py --more 5 -o out.json  # 더보기 5번 클릭 후 저장
    python entry_crawler.py --format csv -o out.csv
    python entry_crawler.py --html saved.html     # 저장된 HTML 파일 파싱 (오프라인)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Iterable

from bs4 import BeautifulSoup, Tag

FEED_URL = "https://gangnambside.com/feed"

COUNT_RE = re.compile(r"(\d+)\s*명")
DATE_RE = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
PAREN_RE = re.compile(r"\(([^)]*)\)")
# 이름 줄에 허용되는 문자: 한글, 영문, 숫자, 공백, 괄호, 점
NAME_LINE_RE = re.compile(r"^[가-힣A-Za-z0-9\s().]+$")


@dataclass
class EntryPost:
    author: str
    author_id: str
    shop_name: str
    shop_slug: str
    time_text: str
    tag: str
    status: str
    content: str
    entry_date: str | None = None  # "10월 19일" 형태 (본문에 있을 때만)
    stated_count: int | None = None  # 본문에 적힌 "N명"
    members: list[str] = field(default_factory=list)  # 출근 명단
    extra_members: list[str] = field(default_factory=list)  # 괄호 안 명단
    crawled_at: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.shop_slug, self.content)


def _text(node: Tag | None) -> str:
    return node.get_text(strip=True) if node else ""


def parse_entry_text(content: str) -> dict:
    """게시글 본문에서 날짜/인원수/명단을 추출한다."""
    date_m = DATE_RE.search(content)
    count_m = COUNT_RE.findall(content)

    members: list[str] = []
    extra: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # 헤더/요약 줄 (예: "앨리스 24명", "10월 16일 금요일", "총 24명", 이모지 제목)
        if COUNT_RE.search(line) or DATE_RE.search(line) or not NAME_LINE_RE.match(line):
            continue
        for group in PAREN_RE.findall(line):
            extra.extend(group.split())
        rest = PAREN_RE.sub(" ", line)
        # 한 글자 토큰(예: "묶")은 이름이 아닌 표기로 보고 제외
        members.extend(tok for tok in rest.split() if len(tok) >= 2)

    return {
        "entry_date": f"{date_m.group(1)}월 {date_m.group(2)}일" if date_m else None,
        "stated_count": int(count_m[0]) if count_m else None,
        "members": members,
        "extra_members": extra,
    }


def parse_article(article: Tag, crawled_at: str = "") -> EntryPost | None:
    body = article.find("div", class_="min-w-0")
    if body is None:
        return None

    author_link = body.find("a", href=re.compile(r"^/users/"))
    shop_link = body.find("a", href=re.compile(r"^/shops/"))
    content_p = body.find("p", class_="whitespace-pre-wrap")
    tag_span = body.find("span", class_="rounded-full", attrs={"role": None})
    status_span = body.find("span", attrs={"role": "status"})

    content = content_p.get_text() if content_p else ""
    content = "\n".join(line.rstrip() for line in content.splitlines()).strip()

    return EntryPost(
        author=_text(author_link),
        author_id=author_link["href"].rsplit("/", 1)[-1] if author_link else "",
        shop_name=_text(shop_link).lstrip("@"),
        shop_slug=shop_link["href"].rsplit("/", 1)[-1] if shop_link else "",
        time_text=_text(body.find("time")),
        tag=_text(tag_span),
        status=_text(status_span),
        content=content,
        crawled_at=crawled_at,
        **parse_entry_text(content),
    )


def parse_feed_html(html: str, crawled_at: str | None = None) -> list[EntryPost]:
    crawled_at = crawled_at or datetime.now().isoformat(timespec="seconds")
    soup = BeautifulSoup(html, "html.parser")
    posts: list[EntryPost] = []
    seen: set[tuple[str, str]] = set()
    for article in soup.find_all("article"):
        post = parse_article(article, crawled_at)
        if post is None or post.key in seen:
            continue
        seen.add(post.key)
        posts.append(post)
    return posts


def fetch_feed_html(
    url: str = FEED_URL,
    more_clicks: int = 0,
    headless: bool = True,
    timeout_ms: int = 30_000,
) -> str:
    """Playwright 로 피드를 렌더링하고 '더보기'를 more_clicks 번 눌러 HTML 을 반환한다."""
    from playwright.sync_api import TimeoutError as PwTimeout
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(locale="ko-KR")
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_selector("article", timeout=timeout_ms)

        for i in range(more_clicks):
            button = page.locator("button", has_text="더보기")
            if button.count() == 0:
                print(f"[info] 더보기 버튼 없음 ({i}번 클릭 후 종료)", file=sys.stderr)
                break
            before = page.locator("article").count()
            button.first.scroll_into_view_if_needed()
            button.first.click()
            try:
                page.wait_for_function(
                    "n => document.querySelectorAll('article').length > n",
                    arg=before,
                    timeout=timeout_ms,
                )
            except PwTimeout:
                print(f"[info] 더 불러올 게시글 없음 ({i + 1}번째 클릭)", file=sys.stderr)
                break

        html = page.content()
        browser.close()
    return html


def write_json(posts: Iterable[EntryPost], fp) -> None:
    json.dump([asdict(p) for p in posts], fp, ensure_ascii=False, indent=2)
    fp.write("\n")


def write_csv(posts: Iterable[EntryPost], fp) -> None:
    fields = [
        "shop_name", "shop_slug", "entry_date", "stated_count", "member_count",
        "members", "extra_members", "time_text", "status", "tag", "author",
        "author_id", "crawled_at", "content",
    ]
    writer = csv.DictWriter(fp, fieldnames=fields)
    writer.writeheader()
    for p in posts:
        row = asdict(p)
        row["member_count"] = len(p.members)
        row["members"] = " ".join(p.members)
        row["extra_members"] = " ".join(p.extra_members)
        writer.writerow({k: row[k] for k in fields})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="gangnambside.com 피드 엔트리 크롤러")
    ap.add_argument("--url", default=FEED_URL, help="피드 URL (기본: %(default)s)")
    ap.add_argument("--more", type=int, default=0, help="'더보기' 클릭 횟수 (기본: 0)")
    ap.add_argument("--html", help="사이트 대신 저장된 HTML 파일을 파싱")
    ap.add_argument("--tag", default="엔트리", help="이 태그의 글만 수집 ('' 이면 전체)")
    ap.add_argument("--shop", action="append", help="가게 slug/이름으로 필터 (여러 번 지정 가능)")
    ap.add_argument("--format", choices=["json", "csv"], default="json")
    ap.add_argument("-o", "--output", help="출력 파일 (기본: stdout)")
    ap.add_argument("--headful", action="store_true", help="브라우저 창을 띄워서 실행")
    args = ap.parse_args(argv)

    if args.html:
        with open(args.html, encoding="utf-8") as f:
            html = f.read()
    else:
        html = fetch_feed_html(args.url, more_clicks=args.more, headless=not args.headful)

    posts = parse_feed_html(html)
    if args.tag:
        posts = [p for p in posts if p.tag == args.tag]
    if args.shop:
        wanted = set(args.shop)
        posts = [p for p in posts if p.shop_slug in wanted or p.shop_name in wanted]

    writer = write_csv if args.format == "csv" else write_json
    if args.output:
        # CSV 는 엑셀에서 한글이 깨지지 않도록 BOM 포함
        encoding = "utf-8-sig" if args.format == "csv" else "utf-8"
        with open(args.output, "w", encoding=encoding, newline="") as f:
            writer(posts, f)
        print(f"[done] {len(posts)}건 저장 -> {args.output}", file=sys.stderr)
    else:
        writer(posts, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
