import logging
import sys
import unittest
from unittest.mock import patch

from util.logger import Logger


@unittest.skipIf(sys.version == "3.9", "Skip on Python 3.9")
class TestLogger(unittest.TestCase):

    def test_missing_input_arg(self):
        with self.assertRaises(TypeError) as err:
            Logger.init_logger(container="Foo")

        self.assertEqual("Logger.init_logger() missing 1 required positional argument: 'loglevel'",
                         str(err.exception))

    def test_missing_input_arg_2(self):
        with self.assertRaises(TypeError) as err:
            Logger.init_logger(loglevel=logging.DEBUG)

        self.assertEqual("Logger.init_logger() missing 1 required positional argument: 'container'",
                         str(err.exception))

    @patch("src.util.logger.os.getenv", return_value="../bar")
    def test_init_logger(self, logdir):
        self.assertEqual(None, Logger.init_logger(loglevel=logging.DEBUG, container="Foo"))

    @patch("src.util.logger.os.getenv", return_value=None)
    def test_logdir_undefined(self, logdir):
        self.assertEqual(None, Logger.init_logger(loglevel=logging.DEBUG, container="Foo"))

    @patch("src.util.logger.os.getenv", return_value="")
    def test_logdir_empty(self, logdir):
        self.assertEqual(None, Logger.init_logger(loglevel=logging.DEBUG, container="Foo"))
