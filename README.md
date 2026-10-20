# entryCrawling

[gangnambside.com/feed](https://gangnambside.com/feed)의 **엔트리** 게시글(가게별 출근 명단)을 수집하는 크롤러입니다.

피드는 Next.js로 브라우저에서 렌더링되고 "더보기" 버튼으로 글을 더 불러오기 때문에,
Playwright(헤드리스 Chromium)로 페이지를 열어 버튼을 누른 뒤 BeautifulSoup으로 `<article>` 카드를 파싱합니다.

## 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

## 사용법

```bash
python entry_crawler.py                          # 첫 화면 수집, JSON을 stdout으로 출력
python entry_crawler.py --more 5 -o entries.json # '더보기' 5번 클릭 후 저장
python entry_crawler.py --format csv -o entries.csv
python entry_crawler.py --shop alice --shop 레이디  # 특정 가게만 (slug 또는 이름)
python entry_crawler.py --tag ""                 # 엔트리 외 모든 태그 글 포함
python entry_crawler.py --html saved.html        # 저장해 둔 HTML 파일 파싱
```

## 수집 항목

| 필드 | 설명 | 예시 |
|---|---|---|
| `shop_name` / `shop_slug` | 가게 이름 / URL slug | `앨리스` / `alice` |
| `entry_date` | 본문에 적힌 날짜 (없으면 `null`) | `10월 19일` |
| `stated_count` | 본문에 적힌 인원수 | `24` |
| `members` | 명단 | `["가희", "준영", ...]` |
| `extra_members` | 괄호 `( )` 안의 명단 | `["민경", "은성"]` |
| `time_text` | 게시 시각 (상대 표기) | `14시간 전` |
| `status` | 상태 배지 | `보통` / `혼잡` / `여유` |
| `tag`, `author`, `author_id`, `content`, `crawled_at` | 태그, 작성자, 원문, 수집 시각 | |

같은 가게의 같은 본문이 중복되면 한 건만 남깁니다.

## 테스트

```bash
python -m unittest -v
```
