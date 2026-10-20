# entryCrawling

[gangnambside.com/feed](https://gangnambside.com/feed)에서 **오늘의 엔트리**(가게별 출근 명단)를 수집하는 크롤러입니다.

피드는 Next.js로 브라우저에서 렌더링되고 "더보기" 버튼으로 글을 더 불러오기 때문에,
Playwright(헤드리스 Chromium)로 페이지를 열어 버튼을 누른 뒤 BeautifulSoup으로 `<article>` 카드를 파싱합니다.

## 추출 규칙

1. 태그가 `엔트리`인 글 중 게시 시각(`14시간 전` 등)이 **20시간 이내**인 글만 오늘 엔트리로 봅니다.
   마지막 글이 20시간을 넘을 때까지 "더보기"를 자동으로 누릅니다.
2. 같은 가게 글이 여러 개면 가장 최신 글 하나만 씁니다.
3. 명단에서 헤더(가게명·인원수, 날짜, `총 N명`)와 괄호 `( )` 안 이름은 제외합니다
   (괄호 안 이름은 본문의 인원수에 포함되지 않음).
4. 가게는 `entry_crawler.py`의 `STORE_NO`에서 storeNo(100~120)로 바꿉니다.
   목록에 없는 가게는 경고를 출력하고 건너뜁니다.

| storeNo | 가게 | slug | storeNo | 가게 | slug |
|---|---|---|---|---|---|
| 100 | 앨리스 | alice | 108 | 베이직 | basic |
| 101 | 퀄리티 | quality | 109 | 임팩트 | impact |
| 102 | 켈리 | kelly | 110 | 피카소 | picasso |
| 103 | 디즈니 | disney | 111 | 원픽 | onepick |
| 104 | 2.4 | 2_4 | 112 | 블렌딩 | blending |
| 105 | 청담동 | cheongdamdong | 113 | 스피드 | speed |
| 106 | 레이디 | lady | 114 | 타이밍 | timing |
| 107 | 어나더 | another | 115 | 파티원 | partyone |

116~120은 새 가게용으로 비워두었습니다.

## 출력

```json
[
  {"storeNo": 100, "workerName": "가희"},
  {"storeNo": 100, "workerName": "준영"}
]
```

## 설치 및 사용법

```bash
pip install -r requirements.txt
playwright install chromium

python entry_crawler.py                        # JSON을 stdout으로 출력
python entry_crawler.py -o entries.json
python entry_crawler.py --format csv -o entries.csv
python entry_crawler.py --max-hours 24         # 기준 시간 변경
python entry_crawler.py --html saved.html      # 저장해 둔 HTML 파일 파싱
```

## 테스트

```bash
python -m unittest -v
```
