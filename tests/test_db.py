import unittest

from entry_db import INSERT_ALLDAY, INSERT_TODAY, save_entries


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def executemany(self, sql, params):
        if self.conn.fail:
            raise RuntimeError("db error")
        self.conn.calls.append((sql, list(params)))


class FakeConn:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []
        self.committed = self.rolled_back = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


ROWS = [{"storeNo": 100, "workerName": "가희"}, {"storeNo": 101, "workerName": "채빈"}]


class SaveEntriesTest(unittest.TestCase):
    def test_inserts_into_both_tables_and_commits(self):
        conn = FakeConn()
        self.assertEqual(save_entries(ROWS, conn), 2)
        expected = [(100, "가희"), (101, "채빈")]
        self.assertEqual(conn.calls, [(INSERT_TODAY, expected), (INSERT_ALLDAY, expected)])
        self.assertTrue(conn.committed)

    def test_rolls_back_on_error(self):
        conn = FakeConn(fail=True)
        with self.assertRaises(RuntimeError):
            save_entries(ROWS, conn)
        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)

    def test_no_rows_is_noop(self):
        conn = FakeConn()
        self.assertEqual(save_entries([], conn), 0)
        self.assertEqual(conn.calls, [])


if __name__ == "__main__":
    unittest.main()
