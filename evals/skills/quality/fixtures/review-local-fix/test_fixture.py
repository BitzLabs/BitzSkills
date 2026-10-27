import unittest
from target import _validate_input


class InputTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(["empty"], _validate_input(""))

    def test_non_empty_ascii(self):
        self.assertEqual([], _validate_input("value"))

    def test_non_empty_japanese(self):
        self.assertEqual([], _validate_input("入力"))


if __name__ == "__main__":
    unittest.main()
