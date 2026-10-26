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

| storeNo | 가게 | slug |
|---|---|---|
| 103 | 블렌딩 | blending |
| 106 | 어나더 | another |
| 107 | 타이밍 | timing |
| 109 | 임팩트 | impact |
| 110 | 피카소 | picasso |

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

## 새 엔트리 자동 저장 (MySQL)

`entry_watcher.py`는 피드를 계속 확인하다가 **새 엔트리 글이 올라오면** 그 글의 명단을
`ENTRY_TODAY`, `ENTRY_ALLDAY` 테이블에 넣습니다.

```sql
INSERT INTO ENTRY_TODAY (storeNo, workerName) VALUES (?, ?)
ON DUPLICATE KEY UPDATE insertCount = insertCount + 1;

INSERT INTO ENTRY_ALLDAY (storeNo, workerName, lastAttendanceAt) VALUES (?, ?, CURRENT_TIMESTAMP)
ON DUPLICATE KEY UPDATE lastAttendanceAt = CURRENT_TIMESTAMP;
```

- 20시간 이내 `엔트리` 글 중 처음 보는 글만 넣습니다. 같은 가게가 글을 다시 올리면 그 글도 새 글로 넣습니다.
- 처리한 글은 `seen_posts.json`에 기록해서, 프로그램을 껐다 켜도 같은 글을 다시 넣지 않습니다
  (피드에 글 ID가 없어 가게 + 본문 내용으로 같은 글인지 판단합니다).
- 네트워크나 DB 오류가 나면 로그만 남기고 다음 주기에 다시 시도합니다.
- Ctrl+C·창 닫기 등 종료 신호를 받으면 진행 중인 확인을 마치고(브라우저·DB 연결 정리) 종료합니다.
  한 번 더 누르면 즉시 강제 종료합니다.
- `ENTRY_TODAY` 초기화는 DB에서 하루 한 번 처리하는 것을 전제로 합니다.

### 설정

프로젝트 폴더에 `.env` 파일을 만들고 접속 정보를 적습니다. `.env`는 `.gitignore`에 들어 있어 커밋되지 않습니다.

```
CHATBOT_MYSQL_HOST=...
CHATBOT_MYSQL_PORT=3306
CHATBOT_MYSQL_USER=...
CHATBOT_MYSQL_PASSWORD=...
CHATBOT_MYSQL_DATABASE=chatBot_DB
```

### 실행

```bash
python entry_watcher.py                   # 60초마다 확인, Ctrl+C 로 종료
python entry_watcher.py --interval 300    # 5분마다 확인
python entry_watcher.py --once            # 한 번만 확인 (작업 스케줄러에 등록할 때)
python entry_watcher.py --skip-existing   # 시작 시점에 이미 있는 글은 넣지 않고 그 이후 글만
```

## 테스트

```bash
python -m unittest -v
```
