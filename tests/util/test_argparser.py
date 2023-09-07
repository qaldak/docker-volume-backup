import logging
import sys
from unittest import TestCase

from src.util.argparser import ArgParser


class TestArgParser(TestCase):

    def test_parse_container_only(self):
        sys.argv = ["main.py", "foo_bar"]

        args = ArgParser.parse_cli_args()
        self.assertEqual(args.container, "foo_bar", "Error: container param not matched")
        self.assertIsNone(args.path, "Error: path param not matched")
        self.assertFalse(args.restart, "Error: restart param not matched")
        self.assertEqual(args.loglevel, logging.DEBUG, "Error: loglevel not matched")

    def test_parse_all_args(self):
        sys.argv = ["main.py", "foo_bar", "-p", "/foo/bar", "--restart", "--debug"]

        args = ArgParser.parse_cli_args()
        self.assertEqual(args.container, "foo_bar", "Error: container param not matched")
        self.assertEqual(args.path, "/foo/bar", "Error: path param not matched")
        self.assertTrue(args.restart, "Error: restart param not matched")
        self.assertEqual(args.loglevel, logging.DEBUG, "Error: loglevel not matched")
