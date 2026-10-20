import unittest
from pathlib import Path

from entry_crawler import parse_entry_text, parse_feed_html

FIXTURE = Path(__file__).parent / "fixtures" / "feed_sample.html"


class ParseFeedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posts = parse_feed_html(FIXTURE.read_text(encoding="utf-8"), crawled_at="t")

    def test_dedupes_repeated_articles(self):
        self.assertEqual([p.shop_slug for p in self.posts], ["alice", "basic", "onepick", "quality"])

    def test_article_fields(self):
        alice = self.posts[0]
        self.assertEqual(alice.author, "강남 비사이드")
        self.assertEqual(alice.author_id, "a63efd69-729c-41c9-bf4b-64b7739f3a15")
        self.assertEqual(alice.shop_name, "앨리스")
        self.assertEqual(alice.time_text, "14시간 전")
        self.assertEqual(alice.tag, "엔트리")
        self.assertEqual(alice.status, "보통")
        self.assertEqual(self.posts[1].status, "혼잡")

    def test_alice_members(self):
        alice = self.posts[0]
        self.assertEqual(alice.stated_count, 24)
        self.assertIsNone(alice.entry_date)
        self.assertEqual(len(alice.members), 24)
        self.assertEqual(alice.members[-1], "수아2")
        self.assertEqual(alice.extra_members, ["민경", "은성"])

    def test_dated_post(self):
        basic = self.posts[1]
        self.assertEqual(basic.entry_date, "10월 16일")
        self.assertEqual(basic.stated_count, 54)
        self.assertEqual(basic.members, ["다미", "미연", "새라", "서영", "희망"])


class ParseEntryTextTest(unittest.TestCase):
    def test_onepick_format(self):
        r = parse_entry_text("🫠OnePick 앤트리🫠\n10월 16일 금요일\n\n예지 주영\n\n묶\n\n총 24명")
        self.assertEqual(r["entry_date"], "10월 16일")
        self.assertEqual(r["stated_count"], 24)
        self.assertEqual(r["members"], ["예지", "주영"])

    def test_inline_parentheses(self):
        r = parse_entry_text("퀄리티 29명\n채빈 소율\nN가영2 (설이 N수안)")
        self.assertEqual(r["members"], ["채빈", "소율", "N가영2"])
        self.assertEqual(r["extra_members"], ["설이", "N수안"])


if __name__ == "__main__":
    unittest.main()
