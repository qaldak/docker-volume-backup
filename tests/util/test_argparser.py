import logging
import sys
from unittest import TestCase

from src.util.argparser import ArgParser


class TestArgParser(TestCase):

    def test_parse_backup_all_args(self):
        sys.argv = ["main.py", "--backup", "foo_bar", "-p", "/foo/bar", "--restart", "--debug"]

        args = ArgParser.parse_cli_args()
        self.assertEqual(args.container, "foo_bar", "Error: container param not matched")
        self.assertEqual(args.path, "/foo/bar", "Error: path param not matched")
        self.assertTrue(args.restart, "Error: restart param not matched")
        self.assertFalse(args.restore, "Error: restore param not matched")
        self.assertEqual(args.loglevel, logging.DEBUG, "Error: loglevel not matched")

    def test_parse_backup_container_only(self):
        sys.argv = ["main.py", "--backup", "foo_bar"]

        args = ArgParser.parse_cli_args()
        self.assertEqual(args.container, "foo_bar", "Error: container param not matched")
        self.assertIsNone(args.path, "Error: path param not matched")
        self.assertFalse(args.restart, "Error: restart param not matched")
        self.assertEqual(args.loglevel, logging.INFO, "Error: loglevel not matched")

    def test_parse_restore_all_args(self):
        sys.argv = ["main.py", "--restore", "--backupfile", "/foo/bar/backup.tar.gz", "-tp", "/data/foo",
                    "--volume", "foobarData", "--debug"]

        args = ArgParser.parse_cli_args()
        # self.assertEqual(args.container, "foo_bar", "Error: container param not matched")
        self.assertTrue(args.restore, "Error: restore param not matched")
        self.assertEqual(args.backupfile, "/foo/bar/backup.tar.gz", "Error: backupfile param not matched")
        self.assertEqual(args.dockervolume, "foobarData", "Error: volume param not matched")
        self.assertEqual(args.targetpath, "/data/foo", "Error: targetpath param not mached")
        self.assertEqual(args.loglevel, logging.DEBUG, "Error: loglevel not matched")

    def test_validate_backup_restore_combi(self):
        sys.argv = ["main.py", "--backup", "foo_bar", "--restore", "--targetpath", "/foo/bar", "--debug"]

        with self.assertRaises(ValueError) as err:
            args = ArgParser.parse_cli_args()
        self.assertEqual(str(err.exception),
                         "Combination of --backup and --restore is not allowed.")

    def test_validate_restore_args_missing_backupfile(self):
        sys.argv = ["main.py", "--restore", "--volume", "foobarData", "--debug"]

        with self.assertRaises(ValueError) as err:
            args = ArgParser.parse_cli_args()
        self.assertEqual(str(err.exception),
                         "Parameter --backupfile, --targetpath and --volume are mandatory in combination with --restore")

    def test_validate_restore_args_missing_targetpath(self):
        sys.argv = ["main.py", "--restore", "--volume", "fooData", "--backupfile",
                    "/foo/bar/backup.tar.gz" "--debug"]

        with self.assertRaises(ValueError) as err:
            args = ArgParser.parse_cli_args()
        self.assertEqual(str(err.exception),
                         "Parameter --backupfile, --targetpath and --volume are mandatory in combination with --restore")

    def test_validate_restore_args_missing_volume(self):
        sys.argv = ["main.py", "--restore", "-tp", "/foo/bar", "--backupfile", "/foo/bar/backup.tar.gz",
                    "--debug"]

        with self.assertRaises(ValueError) as err:
            args = ArgParser.parse_cli_args()
        self.assertEqual(str(err.exception),
                         "Parameter --backupfile, --targetpath and --volume are mandatory in combination with --restore")
