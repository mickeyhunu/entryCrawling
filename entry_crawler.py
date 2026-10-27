"""gangnambside.com/feed 오늘의 엔트리 크롤러.

피드 페이지는 Next.js 로 클라이언트 렌더링되고 "더보기" 버튼으로 게시글을 추가로
불러오기 때문에, Playwright(헤드리스 Chromium)로 페이지를 열어 버튼을 눌러가며
HTML 을 확보한 뒤 BeautifulSoup 으로 <article> 카드를 파싱한다.

게시 시각이 MAX_AGE_HOURS(20시간) 이내인 '엔트리' 글만 오늘 엔트리로 보고,
가게별 최신 글 하나의 명단을 {storeNo, workerName} 행으로 출력한다.

사용 예:
    python entry_crawler.py                       # JSON 을 stdout 으로 출력
    python entry_crawler.py -o entries.json
    python entry_crawler.py --format csv -o entries.csv
    python entry_crawler.py --html saved.html     # 저장된 HTML 파일 파싱 (오프라인)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Iterable

from bs4 import BeautifulSoup, Tag

FEED_URL = "https://gangnambside.com/feed"
ENTRY_TAG = "엔트리"
MAX_AGE_HOURS = 20

# 가게 이름(피드의 @가게명) -> storeNo
STORE_NO = {
    "공공칠": 101,
    "구구단": 102,
    "블렌딩": 103,
    "세이렌": 104,
    "인트로": 105,
    "어나더": 106,
    "타이밍": 107,
    "도깨비": 108,
    "임팩트": 109,
    "피카소": 110,
}

COUNT_RE = re.compile(r"(\d+)\s*명")
DATE_RE = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
PAREN_RE = re.compile(r"[()]")
# 이름에 붙는 영문(N민지, n사랑)과 숫자(조은2, 세나5)
NAME_NOISE_RE = re.compile(r"[A-Za-z0-9]")
# 이름은 두 글자. 셋째 글자부터는 한글로 적은 번호(지연투, 재희삼)로 보고 자른다
NAME_MAX_LEN = 2
# 이름 줄에 허용되는 문자: 한글, 영문, 숫자, 공백, 괄호, 점
NAME_LINE_RE = re.compile(r"^[가-힣A-Za-z0-9\s().]+$")
AGE_RE = re.compile(r"(\d+)\s*(초|분|시간|일|주|개월|달|년)\s*전")
AGE_UNIT_HOURS = {
    "초": 1 / 3600, "분": 1 / 60, "시간": 1, "일": 24,
    "주": 24 * 7, "개월": 24 * 30, "달": 24 * 30, "년": 24 * 365,
}


@dataclass
class EntryPost:
    shop_name: str
    shop_slug: str
    time_text: str
    tag: str
    content: str = ""
    members: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """게시글 식별자. 피드에 글 ID 가 없어서 가게 + 본문으로 만든다."""
        return hashlib.sha1(f"{self.shop_slug}\n{self.content}".encode()).hexdigest()

    @property
    def is_entry(self) -> bool:
        return self.tag == ENTRY_TAG


def parse_age_hours(time_text: str) -> float | None:
    """'14시간 전', '35분 전', '방금 전' 같은 상대 시각을 경과 시간(시간 단위)으로 바꾼다."""
    text = time_text.strip()
    if text.startswith("방금"):
        return 0.0
    m = AGE_RE.search(text)
    if not m:
        return None
    return int(m.group(1)) * AGE_UNIT_HOURS[m.group(2)]


def is_recent(time_text: str, max_hours: float = MAX_AGE_HOURS) -> bool:
    age = parse_age_hours(time_text)
    return age is not None and age < max_hours


def normalize_name(token: str) -> str:
    """'N민지' -> '민지', 'n나라2' -> '나라', '조은2' -> '조은', '지연투' -> '지연'."""
    return NAME_NOISE_RE.sub("", token)[:NAME_MAX_LEN]


def parse_members(content: str) -> list[str]:
    """게시글 본문에서 출근 명단을 추출한다.

    헤더/요약 줄(가게명·인원수, 날짜, '총 N명', 이모지 제목)은 건너뛰고,
    괄호 안 이름도 명단에 포함한다. 이름의 영문/숫자를 떼어낸 뒤 같은 이름은 한 번만 넣는다.
    """
    members: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if COUNT_RE.search(line) or DATE_RE.search(line) or not NAME_LINE_RE.match(line):
            continue
        names = [n for n in map(normalize_name, PAREN_RE.sub(" ", line).split()) if n]
        # 한 글자만 있는 줄(예: "묶")은 이름이 아닌 표기로 보고 제외
        if len(names) == 1 and len(names[0]) == 1:
            continue
        members.extend(n for n in names if n not in members)
    return members


def parse_article(article: Tag) -> EntryPost | None:
    body = article.find("div", class_="min-w-0")
    if body is None:
        return None

    shop_link = body.find("a", href=re.compile(r"^/shops/"))
    content_p = body.find("p", class_="whitespace-pre-wrap")
    tag_span = body.find("span", class_="rounded-full", attrs={"role": None})
    time_el = body.find("time")
    content = content_p.get_text().strip() if content_p else ""

    return EntryPost(
        shop_name=shop_link.get_text(strip=True).lstrip("@") if shop_link else "",
        shop_slug=shop_link["href"].rsplit("/", 1)[-1] if shop_link else "",
        time_text=time_el.get_text(strip=True) if time_el else "",
        tag=tag_span.get_text(strip=True) if tag_span else "",
        content=content,
        members=parse_members(content),
    )


def parse_feed_html(html: str) -> list[EntryPost]:
    soup = BeautifulSoup(html, "html.parser")
    return [p for p in map(parse_article, soup.find_all("article")) if p is not None]


def todays_entries(
    posts: Iterable[EntryPost], max_hours: float = MAX_AGE_HOURS
) -> list[dict]:
    """오늘(max_hours 이내) 엔트리 글에서 가게별 최신 글의 명단을 행으로 만든다."""
    rows: list[dict] = []
    done: set[str] = set()
    for post in posts:  # 피드는 최신순이므로 가게별 첫 글이 최신 글
        if not post.is_entry or not is_recent(post.time_text, max_hours):
            continue
        if post.shop_slug in done:
            continue
        post_rows = rows_for_post(post)
        if post_rows is None:
            continue
        done.add(post.shop_slug)
        rows.extend(post_rows)
    return rows


def rows_for_post(post: EntryPost) -> list[dict] | None:
    """게시글 하나의 명단을 {storeNo, workerName} 행으로 만든다. storeNo 미지정 가게는 None."""
    store_no = STORE_NO.get(post.shop_name)
    if store_no is None:
        print(
            f"[warn] storeNo 미지정 가게 건너뜀: {post.shop_name} ({post.shop_slug})"
            " -> STORE_NO 에 추가하세요",
            file=sys.stderr,
        )
        return None
    return [{"storeNo": store_no, "workerName": name} for name in post.members]


def fetch_feed_html(
    url: str = FEED_URL,
    max_hours: float = MAX_AGE_HOURS,
    max_clicks: int = 20,
    headless: bool = True,
    timeout_ms: int = 30_000,
) -> str:
    """Playwright 로 피드를 렌더링하고, 마지막 글이 max_hours 를 넘길 때까지 '더보기'를 누른다."""
    from playwright.sync_api import TimeoutError as PwTimeout
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        # 페이지 로딩 중 오류/중단이 나도 브라우저 프로세스가 남지 않도록 항상 닫는다
        try:
            page = browser.new_page(locale="ko-KR")
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_selector("article", timeout=timeout_ms)

            for i in range(max_clicks):
                last_time = page.locator("article time").last.inner_text()
                if not is_recent(last_time, max_hours):
                    break
                button = page.locator("button", has_text="더보기")
                if button.count() == 0:
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
        finally:
            browser.close()
    return html


def write_json(rows: list[dict], fp) -> None:
    json.dump(rows, fp, ensure_ascii=False, indent=2)
    fp.write("\n")


def write_csv(rows: list[dict], fp) -> None:
    writer = csv.DictWriter(fp, fieldnames=["storeNo", "workerName"])
    writer.writeheader()
    writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="gangnambside.com 오늘의 엔트리 크롤러")
    ap.add_argument("--url", default=FEED_URL, help="피드 URL (기본: %(default)s)")
    ap.add_argument("--html", help="사이트 대신 저장된 HTML 파일을 파싱")
    ap.add_argument("--max-hours", type=float, default=MAX_AGE_HOURS,
                    help="이 시간 이내 글만 오늘 엔트리로 봄 (기본: %(default)s)")
    ap.add_argument("--format", choices=["json", "csv"], default="json")
    ap.add_argument("-o", "--output", help="출력 파일 (기본: stdout)")
    ap.add_argument("--headful", action="store_true", help="브라우저 창을 띄워서 실행")
    args = ap.parse_args(argv)

    if args.html:
        with open(args.html, encoding="utf-8") as f:
            html = f.read()
    else:
        html = fetch_feed_html(args.url, max_hours=args.max_hours, headless=not args.headful)

    rows = todays_entries(parse_feed_html(html), args.max_hours)

    writer = write_csv if args.format == "csv" else write_json
    if args.output:
        # CSV 는 엑셀에서 한글이 깨지지 않도록 BOM 포함
        encoding = "utf-8-sig" if args.format == "csv" else "utf-8"
        with open(args.output, "w", encoding=encoding, newline="") as f:
            writer(rows, f)
    else:
        writer(rows, sys.stdout)
    stores = len({r["storeNo"] for r in rows})
    print(f"[done] 가게 {stores}곳, {len(rows)}명", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
