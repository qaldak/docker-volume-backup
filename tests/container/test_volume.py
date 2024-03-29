import warnings
from unittest import TestCase
from unittest.mock import patch

from python_on_whales import DockerException

from container.volume import Volume, Recovery


class TestVolume(TestCase):
    @patch("src.container.volume.docker.volume.exists", return_value=True)
    def test_exists_true(self, mock_volume):
        volume = Volume("foo")
        self.assertTrue(volume.exists(), f"Volume '{volume.name}' not found, but should")

    @patch("src.container.volume.docker.volume.exists", return_value=False)
    def test_exists_false(self, mock_volume):
        volume = Volume("foo")
        self.assertFalse(volume.exists(), f"Volume '{volume.name}' found, but should not")

    @patch("src.container.volume.docker.volume.exists", return_value=True)
    @patch("src.container.volume.docker.volume.create", return_value="foo_data")
    def test_create_successfully(self, mock_volume, mock_exists):
        with self.assertLogs("container.volume", level="INFO") as log:
            Volume("foo").create()
            self.assertEqual(
                ["INFO:container.volume:Volume 'foo_data' successfully created."], log.output)

    @patch("src.container.volume.docker.volume.exists", return_value=False)
    @patch("src.container.volume.docker.volume.create", return_value="foo_data")
    def test_create_but_not_exists(self, mock_volume, mock_exists):
        with self.assertLogs("container.volume", level="ERROR") as log:
            with self.assertRaises(AttributeError) as err:
                new_volume = Volume("foo").create()
            self.assertEqual("Error: volume 'foo_data' created, but not exists.", str(err.exception))
            self.assertEqual('["ERROR:container.volume:Error: volume \'foo_data\' created, but not exists."]',
                             str(log.output))

    @patch("src.container.volume.docker.volume.create", side_effect=DockerException(
        command_launched=["docker volume create foo_data"], return_code=1,
        stderr=b"error during connect: this error may indicate that the docker daemon is not running"))
    def test_docker_daemon_not_running(self, mock_error):
        with self.assertRaises(DockerException) as err:
            new_volume = Volume("foo").create()
        self.assertEqual(1, err.exception.return_code)
        self.assertEqual("error during connect: this error may indicate that the docker daemon is not running",
                         str(err.exception.stderr))
        log = self.assertLogs("container.volume", level="ERROR")
        print(log.logger_name)

    @patch("src.container.volume.docker.volume.list",
           return_value=["python_on_whales.Volume(name='foo_data', driver=local)"])
    def test_docker_volume_in_use(self, mock_volume):
        self.assertTrue(Volume("foo").in_use(), "Volume not in use, but should.")

    @patch("src.container.volume.docker.volume.list", return_value=[])
    def test_docker_volume_not_in_use(self, mock_volume):
        self.assertFalse(Volume("foo").in_use(), "Volume not in use, but should.")


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
    @patch("src.container.volume.docker.run", return_value="4")
    def test_check_recovery_successful(self, mock_docker_vol_content, mock_print):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        recovery.check_recovery()
        mock_print.assert_called_with("Recovery successful. Number of restored files matches: 4 vs 4")

    @patch("warnings.warn")
    @patch("src.container.volume.docker.run", return_value="7")
    def test_check_recovery_failed(self, mock_docker_vol_content, mock_warning):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        with warnings.catch_warnings(record=True) as w:
            recovery.check_recovery()
            mock_warning.assert_called_with(
                "Number of restored files does not match the content of tar file: 7 vs 4. Check manually or run again in debug mode for more details.")

    @patch("src.container.volume.docker.run", return_value="Foobar")
    def test_check_recovery_error(self, mock_docker_vol_content):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        with self.assertRaises(ValueError) as err:
            recovery.check_recovery()

        self.assertEqual("invalid literal for int() with base 10: 'Foobar'", str(err.exception))
