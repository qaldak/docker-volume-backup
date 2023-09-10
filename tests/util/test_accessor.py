from unittest import TestCase
from unittest.mock import patch

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
    def test_backup_dir_created(self, mock_dir, mock_create):
        backup_dir = BackupDir("/Foo", "Bar")
        self.assertIsNone(backup_dir.create(), "Directory not found, but should")

    def test_create(self):
        assert False
