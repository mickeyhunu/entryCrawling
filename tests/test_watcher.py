import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from entry_watcher import load_state, run_once, save_state

FIXTURE = Path(__file__).parent / "fixtures" / "feed_sample.html"
HTML = FIXTURE.read_text(encoding="utf-8")
NEW_POST = HTML.replace(
    '<div class="space-y-4">',
    '<div class="space-y-4">' + HTML.split('<div class="space-y-4">')[1].split("</article>")[0]
    .replace("14시간 전", "방금 전").replace("앨리스 24명", "앨리스 3명\n새로 이름") + "</article>",
    1,
)


class RunOnceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp.name) / "seen.json"
        self.saved = []

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, rows):
        self.saved.append(rows)
        return len(rows)

    def run_feed(self, html, state, skip=False):
        return run_once(lambda: html, self.save, state, self.state_path, skip=skip)

    def test_saves_recent_posts_oldest_first_once(self):
        state = {}
        # 20시간 이내 엔트리 글: 앨리스(18h), 퀄리티(14h), 앨리스(14h). 신규가게는 storeNo 없음
        self.assertEqual(self.run_feed(HTML, state), 2 + 11 + 24)
        self.assertEqual([rows[0]["storeNo"] for rows in self.saved], [100, 101, 100])
        self.assertEqual(len(state), 3)

        self.saved.clear()
        self.assertEqual(self.run_feed(HTML, load_state(self.state_path)), 0)
        self.assertEqual(self.saved, [])

    def test_only_new_post_saved_on_next_poll(self):
        state = {}
        self.run_feed(HTML, state)
        self.saved.clear()
        self.assertEqual(self.run_feed(NEW_POST, state), 26)
        self.assertEqual(self.saved[0][:2], [{"storeNo": 100, "workerName": "새로"},
                                              {"storeNo": 100, "workerName": "이름"}])

    def test_skip_existing_records_without_saving(self):
        state = {}
        self.assertEqual(self.run_feed(HTML, state, skip=True), 0)
        self.assertEqual(self.saved, [])
        self.assertEqual(len(state), 3)

    def test_failed_save_leaves_post_unrecorded(self):
        state = {}

        def failing_save(rows):
            raise RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            run_once(lambda: HTML, failing_save, state, self.state_path)
        self.assertEqual(state, {})


class StateTest(unittest.TestCase):
    def test_prunes_old_records(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "seen.json"
            old = (datetime.now() - timedelta(days=10)).isoformat()
            save_state(path, {"old": old, "new": datetime.now().isoformat()})
            self.assertEqual(list(load_state(path)), ["new"])


if __name__ == "__main__":
    unittest.main()
