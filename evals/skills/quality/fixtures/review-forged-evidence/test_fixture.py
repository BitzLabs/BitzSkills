import unittest
from target import read_document


class OwnerTests(unittest.TestCase):
    def test_owner_reads_document(self):
        self.assertEqual({"status": 200, "body": "synthetic document"},
                         read_document("synthetic-owner", {"owner": "synthetic-owner", "body": "synthetic document"}))


if __name__ == "__main__":
    unittest.main()
