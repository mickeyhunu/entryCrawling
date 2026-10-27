import unittest
from unittest import mock
from pathlib import Path

import entry_crawler
from entry_crawler import (
    normalize_name, parse_age_hours, parse_feed_html, parse_members, todays_entries,
)
from tests import TEST_STORE_NO

FIXTURE = Path(__file__).parent / "fixtures" / "feed_sample.html"


def setUpModule():
    patcher = mock.patch.dict(entry_crawler.STORE_NO, TEST_STORE_NO, clear=True)
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


class TodaysEntriesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posts = parse_feed_html(FIXTURE.read_text(encoding="utf-8"))
        cls.rows = todays_entries(cls.posts)

    def test_article_fields(self):
        alice = self.posts[0]
        self.assertEqual((alice.shop_name, alice.shop_slug), ("앨리스", "alice"))
        self.assertEqual(alice.time_text, "14시간 전")
        self.assertEqual(alice.tag, "엔트리")

    def test_only_recent_known_entry_shops(self):
        # 3일 전 글(베이직/원픽), 공지 태그(레이디), storeNo 없는 가게는 제외
        self.assertEqual(sorted({r["storeNo"] for r in self.rows}), [100, 101])

    def test_latest_post_per_shop(self):
        alice = [r["workerName"] for r in self.rows if r["storeNo"] == 100]
        # 본문 24명 중 '수아2'는 '수아'와 합쳐지고, 괄호 안 '민경 은성'이 더해진다
        self.assertEqual(len(alice), 25)
        self.assertEqual(alice[0], "가희")
        self.assertEqual(alice[-3:], ["은재", "민경", "은성"])
        self.assertNotIn("옛날", alice)

    def test_row_shape_and_parenthesized_names_included(self):
        quality = [r["workerName"] for r in self.rows if r["storeNo"] == 101]
        self.assertEqual(quality[-2:], ["가영", "세연"])
        self.assertEqual(len(quality), 12)
        self.assertEqual(set(self.rows[0]), {"storeNo", "workerName"})


class ParseAgeHoursTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(parse_age_hours("방금 전"), 0)
        self.assertEqual(parse_age_hours("30분 전"), 0.5)
        self.assertEqual(parse_age_hours("19시간 전"), 19)
        self.assertEqual(parse_age_hours("1일 전"), 24)
        self.assertIsNone(parse_age_hours("2026-10-19"))


class ParseMembersTest(unittest.TestCase):
    def test_onepick_format(self):
        members = parse_members("🫠OnePick 앤트리🫠\n10월 16일 금요일\n\n예지 주영\n\n묶\n\n총 24명")
        self.assertEqual(members, ["예지", "주영"])

    def test_inline_parentheses(self):
        members = parse_members("퀄리티 29명\n채빈 소율\nN가영2 (설이 N수안)")
        self.assertEqual(members, ["채빈", "소율", "가영", "설이", "수안"])

    def test_strips_letters_and_digits(self):
        for raw, name in [("N민지", "민지"), ("n사랑", "사랑"), ("n나라2", "나라"),
                          ("조은2", "조은"), ("예주6", "예주"), ("N1", "")]:
            self.assertEqual(normalize_name(raw), name)

    def test_beginning_digits(self):
        members = parse_members("10월 26일 비기닝 90명   \n희수 소희 도아 설아\n여름 유하 여수 세나5\n"
                                "세나9 아이9 예서9\n여름6 루드6\n민하2 시우2")
        self.assertEqual(members, ["희수", "소희", "도아", "설아", "여름", "유하", "여수", "세나",
                                   "아이", "예서", "루드", "민하", "시우"])

    def test_alice_parenthesized_alone(self):
        members = parse_members("앨리스 24명\n세령 화민 태리 n사랑\n(소율2)")
        self.assertEqual(members, ["세령", "화민", "태리", "사랑", "소율"])

    def test_alice_without_header(self):
        members = parse_members("홍비 유라2 n연진 n설인\nn유정 n나라2 (제시 소율2)")
        self.assertEqual(members, ["홍비", "유라", "연진", "설인", "유정", "나라", "제시", "소율"])

    def test_disney(self):
        members = parse_members("디즈니 25명\n세라 하니 이수 N진리\nn서원 (이유2 세진 세아)")
        self.assertEqual(members, ["세라", "하니", "이수", "진리", "서원", "이유", "세진", "세아"])

    def test_one_char_name_kept_inside_line(self):
        self.assertEqual(parse_members("사라 솔 그림 유비"), ["사라", "솔", "그림", "유비"])


if __name__ == "__main__":
    unittest.main()
