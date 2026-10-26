"""크롤링한 엔트리 행을 MySQL 의 ENTRY_TODAY / ENTRY_ALLDAY 테이블에 저장한다.

접속 정보는 환경 변수 또는 프로젝트 폴더의 .env 파일에서 읽는다:
    CHATBOT_MYSQL_HOST, CHATBOT_MYSQL_PORT, CHATBOT_MYSQL_USER,
    CHATBOT_MYSQL_PASSWORD, CHATBOT_MYSQL_DATABASE
"""

from __future__ import annotations

import os
from pathlib import Path

INSERT_TODAY = """
INSERT INTO ENTRY_TODAY (storeNo, workerName)
VALUES (%s, %s)
ON DUPLICATE KEY UPDATE
  insertCount = insertCount + 1
"""

INSERT_ALLDAY = """
INSERT INTO ENTRY_ALLDAY (storeNo, workerName, lastAttendanceAt)
VALUES (%s, %s, CURRENT_TIMESTAMP)
ON DUPLICATE KEY UPDATE
  lastAttendanceAt = CURRENT_TIMESTAMP
"""

ENV_PREFIX = "CHATBOT_MYSQL_"


def load_db_config() -> dict:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).with_name(".env"))
    missing = [
        key for key in ("HOST", "USER", "PASSWORD", "DATABASE")
        if not os.getenv(ENV_PREFIX + key)
    ]
    if missing:
        names = ", ".join(ENV_PREFIX + k for k in missing)
        raise SystemExit(f"[error] DB 접속 정보가 없습니다: {names} (.env 파일을 확인하세요)")
    return {
        "host": os.environ[ENV_PREFIX + "HOST"],
        "port": int(os.getenv(ENV_PREFIX + "PORT", "3306")),
        "user": os.environ[ENV_PREFIX + "USER"],
        "password": os.environ[ENV_PREFIX + "PASSWORD"],
        "database": os.environ[ENV_PREFIX + "DATABASE"],
        "charset": "utf8mb4",
        "connect_timeout": 10,
    }


def save_entries(rows: list[dict], conn=None) -> int:
    """rows([{storeNo, workerName}, ...])를 두 테이블에 한 트랜잭션으로 저장한다."""
    if not rows:
        return 0

    own_conn = conn is None
    if own_conn:
        import pymysql

        conn = pymysql.connect(**load_db_config())
    params = [(r["storeNo"], r["workerName"]) for r in rows]
    try:
        with conn.cursor() as cur:
            cur.executemany(INSERT_TODAY, params)
            cur.executemany(INSERT_ALLDAY, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if own_conn:
            conn.close()
    return len(params)
