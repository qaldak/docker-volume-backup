from unittest import TestCase

from util.accessor import set_backup_dir


class TestAccessor(TestCase):
    def test_backup_dir_success(self):
        self.assertEqual(set_backup_dir("/Foo", "Container"), "/Foo/Container", "Invalid docker directory")

    def test_backup_dir_path_not_set(self):
        with self.assertRaises(ValueError):
            set_backup_dir("", "Docker")
