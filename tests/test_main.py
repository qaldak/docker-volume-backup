import unittest

from src.main import main


class TestMain(unittest.TestCase):

    def test_main(self):
        self.assertEqual(main("b"), "Bar", "Wrong answer")
