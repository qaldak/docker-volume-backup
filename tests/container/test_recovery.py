import warnings
from unittest import TestCase
from unittest.mock import patch

from docker_volume_backup.container.recovery import Recovery


class TestRecovery(TestCase):
    def test_recovery_determine_strip_length(self):
        recovery = Recovery(backup_file="/backup/path/foo.xyz", docker_volume="foo_data", target_path="/foo/bar/baz")
        self.assertEqual(recovery._determine_strip_length(), 3, "Strip length not correct")

    def test_recovery_determine_cmp_method_gz(self):
        recovery = Recovery(backup_file="/backup/path/foo.xyz.gz", docker_volume="foo_data", target_path="/foo/bar/baz")
        self.assertEqual(recovery._determine_cmp_method(), "-z", "Determine compression method failed")

    def test_recovery_determine_cmp_method_bz2(self):
        recovery = Recovery(backup_file="/backup/path/foo.xyz.bz2", docker_volume="foo_data",
                            target_path="/foo/bar/baz")
        self.assertEqual(recovery._determine_cmp_method(), "-j", "Determine compression method failed")

    def test_recovery_create_backup_cmd(self):
        recovery = Recovery(backup_file="/backup/path/foo.xyz.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")
        self.assertEqual(recovery._create_tar_cmd(),
                         ["tar", "-x", "-z", "-v", "-f", "/backup/foo.xyz.gz", "--strip-components=3", "-C",
                          "/foo/bar/baz"], "Backup command failed")

    def test_create_list_cmd(self):
        recovery = Recovery(backup_file="/backup/path/foo.xyz.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz/to/the/file")

        self.assertEqual(recovery._create_list_cmd(), ['ash', '-c', 'find /foo -mindepth 1 | wc -l'],
                         "Tar command failed")

    @patch("builtins.print")
    @patch("docker_volume_backup.container.recovery.docker.run", return_value="4")
    def test_check_recovery_successful(self, mock_docker_vol_content, mock_print):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        recovery.check_recovery()
        mock_print.assert_called_with("Recovery successful. Number of restored files matches: 4 vs 4")

    @patch("warnings.warn")
    @patch("docker_volume_backup.container.recovery.docker.run", return_value="7")
    def test_check_recovery_failed(self, mock_docker_vol_content, mock_warning):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        with warnings.catch_warnings(record=True) as w:
            recovery.check_recovery()
            mock_warning.assert_called_with(
                "Number of restored files does not match the content of tar file: 7 vs 4. Check manually or run again in debug mode for more details.")

    @patch("docker_volume_backup.container.recovery.docker.run", return_value="Foobar")
    def test_check_recovery_error(self, mock_docker_vol_content):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        with self.assertRaises(ValueError) as err:
            recovery.check_recovery()

        self.assertEqual("invalid literal for int() with base 10: 'Foobar'", str(err.exception))
