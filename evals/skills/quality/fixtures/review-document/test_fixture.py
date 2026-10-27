import unittest
from target import _validate_input


class InputTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(["empty"], _validate_input(""))


if __name__ == "__main__":
    unittest.main()
