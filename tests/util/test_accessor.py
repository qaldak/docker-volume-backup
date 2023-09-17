from unittest import TestCase
from unittest.mock import patch

import util.accessor
from util.accessor import BackupDir


class TestAccessor(TestCase):
    def test_backup_dir_success(self):
        backup_dir = BackupDir("/Foo", "Bar")
        self.assertEqual(backup_dir.path, "/Foo/Bar", "Invalid container directory")

    def test_backup_dir_path_not_set(self):
        with self.assertRaises(ValueError):
            BackupDir("", "Bar")

    @patch("src.util.accessor.os.path.isdir", return_value=True)
    def test_backup_dir_exists(self, mock_dir):
        backup_dir = BackupDir("/Foo", "Bar")
        self.assertIsNone(backup_dir.create(), "Directory not found, but should")

    @patch("src.util.accessor.os.path.isdir", return_value=False)
    @patch("src.util.accessor.os.makedirs", return_value=None)
    def test_backup_dir_created(self, mock_dir, mock_makedirs):
        backup_dir = BackupDir("/Foo", "Bar")
        self.assertIsNone(backup_dir.create(), "Directory not found, but should")

    @patch("src.util.accessor.os.path.isdir", return_value=False)
    @patch("src.util.accessor.os.makedirs", side_effect=FileExistsError("Directory already exists"))
    def test_backup_dir_error(self, mock_dir, mock_makedir):
        backup_dir = BackupDir("/Foo", "Bar")
        with self.assertLogs("util.accessor", level="INFO") as log:
            backup_dir.create()
            self.assertEqual(
                ["INFO:util.accessor:Backup directory '/Foo/Bar' exists. Directory already exists"],
                log.output)

    def test_get_hostname(self):
        hostname = util.accessor.LocalHost.get_hostname()
        self.assertTrue(hostname.islower())
