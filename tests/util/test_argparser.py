import logging
import sys
from unittest import TestCase

from src.util.argparser import ArgParser


class TestArgParser(TestCase):

    def test_parse_container_only_for_backup(self):
        sys.argv = ["main.py", "foo_bar"]

        args = ArgParser.parse_cli_args()
        self.assertEqual(args.container, "foo_bar", "Error: container param not matched")
        self.assertIsNone(args.path, "Error: path param not matched")
        self.assertFalse(args.restart, "Error: restart param not matched")
        self.assertEqual(args.loglevel, logging.INFO, "Error: loglevel not matched")

    def test_parse_all_args_for_backup(self):
        sys.argv = ["main.py", "foo_bar", "-p", "/foo/bar", "--restart", "--debug"]

        args = ArgParser.parse_cli_args()
        self.assertEqual(args.container, "foo_bar", "Error: container param not matched")
        self.assertEqual(args.path, "/foo/bar", "Error: path param not matched")
        self.assertTrue(args.restart, "Error: restart param not matched")
        self.assertFalse(args.restore, "Error: restore param not matched")
        self.assertEqual(args.loglevel, logging.DEBUG, "Error: loglevel not matched")

    def test_validate_args_failed_backup_volume(self):
        sys.argv = ["main.py", "foo_bar", "-p", "/foo/bar", "--restart", "--volume", "foobarData", "--debug"]

        with self.assertRaises(ValueError) as err:
            args = ArgParser.parse_cli_args()
        self.assertEqual(str(err.exception),
                         "Parameters --backupfile and --volume only available in combination with --restore")

    def test_validate_args_failed_backup_backupfile(self):
        sys.argv = ["main.py", "foo_bar", "--restart", "--backupfile", "/foo/bar/backup.tar.gz", "--debug"]

        with self.assertRaises(ValueError) as err:
            args = ArgParser.parse_cli_args()
        self.assertEqual(str(err.exception),
                         "Parameters --backupfile and --volume only available in combination with --restore")

    def test_validate_args_failed_restore_path(self):
        sys.argv = ["main.py", "foo_bar", "-p", "/foo/bar", "--restart", "--restore", "--debug"]

        with self.assertRaises(ValueError) as err:
            args = ArgParser.parse_cli_args()
        self.assertEqual(str(err.exception),
                         "Parameter --path and --restart not available in combination with --restore")

    def test_validate_args_failed_restore_restart(self):
        sys.argv = ["main.py", "foo_bar", "--restart", "--restore", "--debug"]

        with self.assertRaises(ValueError) as err:
            args = ArgParser.parse_cli_args()
        self.assertEqual(str(err.exception),
                         "Parameter --path and --restart not available in combination with --restore")

    def test_validate_args_failed_restore_backupfile(self):
        sys.argv = ["main.py", "foo_bar", "--restore", "--volume", "foobarData", "--debug"]

        with self.assertRaises(ValueError) as err:
            args = ArgParser.parse_cli_args()
        self.assertEqual(str(err.exception),
                         "Parameter --backupfile and --volume are mandatory in combination with --restore")

    def test_validate_args_failed_restore_volume(self):
        sys.argv = ["main.py", "foo_bar", "--restore", "--backupfile", "/foo/bar/backup.tar.gz", "--debug"]

        with self.assertRaises(ValueError) as err:
            args = ArgParser.parse_cli_args()
        self.assertEqual(str(err.exception),
                         "Parameter --backupfile and --volume are mandatory in combination with --restore")

    def test_parse_all_args_for_restore(self):
        sys.argv = ["main.py", "foo_bar", "--restore", "--backupfile", "/foo/bar/backup.tar.gz", "--volume",
                    "foobarData", "--debug"]

        args = ArgParser.parse_cli_args()
        self.assertEqual(args.container, "foo_bar", "Error: container param not matched")
        self.assertTrue(args.restore, "Error: restore param not matched")
        self.assertEqual(args.backupfile, "/foo/bar/backup.tar.gz", "Error: backupfile param not matched")
        self.assertEqual(args.targetvolume, "foobarData", "Error: volume param not matched")
        self.assertEqual(args.loglevel, logging.DEBUG, "Error: loglevel not matched")
