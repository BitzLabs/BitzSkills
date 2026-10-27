import unittest
from target import validate_input


class EmptyInputTests(unittest.TestCase):
    def test_one_error(self):
        self.assertEqual(1, len(validate_input("")))


if __name__ == "__main__":
    unittest.main()
