import logging
import unittest

from util.logger import Logger


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

    def test_init_logger(self):
        self.assertEqual(None, Logger.init_logger(loglevel=logging.DEBUG, container="Foo"))
