import unittest
from unittest import mock
from pathlib import Path

import entry_crawler
from entry_crawler import parse_age_hours, parse_feed_html, parse_members, todays_entries
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
        self.assertEqual(len(alice), 24)
        self.assertEqual(alice[0], "가희")
        self.assertEqual(alice[-1], "수아2")
        self.assertNotIn("옛날", alice)

    def test_row_shape_and_parenthesized_names_excluded(self):
        quality = [r["workerName"] for r in self.rows if r["storeNo"] == 101]
        self.assertEqual(len(quality), 11)
        self.assertNotIn("세연", quality)
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
        self.assertEqual(members, ["채빈", "소율", "N가영2"])


if __name__ == "__main__":
    unittest.main()
