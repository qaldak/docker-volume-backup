from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from python_on_whales import DockerException

from docker_volume_backup.container.backup import Backup


class MockContainer:

    def __init__(self) -> None:
        super().__init__()
        self.name = "foo_bar"
        self.docker_volumes = ["/foo/data", "/foo/config"]
        self.docker_bindings = ["/bar/log"]
        self.has_docker_volume = True
        self.has_docker_bindings = True


class MockBackupDir:

    def __init__(self) -> None:
        super().__init__()
        self.path = "/foo/backup"


class TestBackup(TestCase):

    def test_run_backup_no_volumes(self):
        backup_dir = MockBackupDir()
        container = MockContainer()
        container.has_docker_volume = False
        container.has_docker_bindings = False

        with self.assertRaises(AssertionError) as err:
            Backup(container=container, backup_dir=backup_dir).run_backup()

        self.assertEqual("No volumes to backup", str(err.exception))

    @patch("docker_volume_backup.container.backup.docker.run",
           side_effect=DockerException(command_launched=[""], return_code=115))
    def test_run_backup_docker_exception(self, error):
        backup_dir = MockBackupDir()
        container = MockContainer()
        with self.assertRaises(DockerException) as err:
            Backup(container=container, backup_dir=backup_dir).run_backup()
        self.assertEqual(115, err.exception.return_code)

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.os.path.getsize", return_value=987654321)
    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    @patch("docker_volume_backup.container.backup.docker.run", return_value="Everything is allright")
    def test_run_backup_successful(self, tmp, hostname, filesize, should_refresh):
        backup_dir = MockBackupDir()
        container = MockContainer()
        with self.assertLogs("docker_volume_backup.container.backup", level="INFO") as log:
            Backup(container=container, backup_dir=backup_dir).run_backup()
            self.assertEqual([
                "INFO:docker_volume_backup.container.backup:Execute Volume backup for container 'foo_bar'. tar "
                "command: ['tar', 'c', '-z', '-f', "
                "'/backup/groot-foo_bar-volume-backup.tar.gz.tmp', '-C', '/', 'foo/data', 'foo/config', "
                "'bar/log']",
                "INFO:docker_volume_backup.container.backup:Volume backup for container 'foo_bar' successful. "
                'Duration: 0:00:00, Backup size: 987654321'],
                log.output)

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.os.path.getsize", return_value=1234)
    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    @patch("docker_volume_backup.container.backup.docker.run", return_value="")
    def test_run_backup_replaces_backup_file_only_after_tar(self, docker_run, hostname, filesize, should_refresh):
        Backup(container=MockContainer(), backup_dir=MockBackupDir()).run_backup()

        commands = [call.args[1] for call in docker_run.call_args_list]
        self.assertEqual(2, len(commands), commands)
        self.assertEqual("tar", commands[0][0])
        self.assertEqual("/backup/groot-foo_bar-volume-backup.tar.gz.tmp", commands[0][commands[0].index("-f") + 1])
        self.assertEqual(["mv", "-f", "/backup/groot-foo_bar-volume-backup.tar.gz.tmp",
                          "/backup/groot-foo_bar-volume-backup.tar.gz"], commands[1])

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    @patch("docker_volume_backup.container.backup.docker.run")
    def test_run_backup_failing_tar_keeps_last_backup_and_removes_tmp_file(self, docker_run, hostname, should_refresh):
        docker_run.side_effect = [DockerException(command_launched=["tar"], return_code=1), ""]

        with self.assertRaises(DockerException) as err:
            Backup(container=MockContainer(), backup_dir=MockBackupDir()).run_backup()

        self.assertEqual(1, err.exception.return_code)
        commands = [call.args[1] for call in docker_run.call_args_list]
        self.assertEqual(2, len(commands), commands)
        self.assertEqual("tar", commands[0][0])
        self.assertEqual(["rm", "-f", "/backup/groot-foo_bar-volume-backup.tar.gz.tmp"], commands[1])
        self.assertNotIn("mv", [command[0] for command in commands])

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    @patch("docker_volume_backup.container.backup.docker.run")
    def test_run_backup_failing_replace_removes_tmp_file(self, docker_run, hostname, should_refresh):
        docker_run.side_effect = ["", DockerException(command_launched=["mv"], return_code=1), ""]

        with self.assertRaises(DockerException):
            Backup(container=MockContainer(), backup_dir=MockBackupDir()).run_backup()

        commands = [call.args[1][0] for call in docker_run.call_args_list]
        self.assertEqual(["tar", "mv", "rm"], commands)

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    @patch("docker_volume_backup.container.backup.docker.run")
    def test_run_backup_failing_cleanup_does_not_mask_backup_error(self, docker_run, hostname, should_refresh):
        docker_run.side_effect = [DockerException(command_launched=["tar"], return_code=2),
                                  DockerException(command_launched=["rm"], return_code=125)]

        with self.assertLogs("docker_volume_backup.container.backup", level="WARNING") as log:
            with self.assertRaises(DockerException) as err:
                Backup(container=MockContainer(), backup_dir=MockBackupDir()).run_backup()

        self.assertEqual(2, err.exception.return_code)
        self.assertTrue(any("could not be removed" in line for line in log.output), log.output)

    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    def test_create_tar_cmd_default(self, host):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        tar_cmd = backup._create_tar_cmd()
        assert ["tar", "c", "-z", "-f", f"/backup/groot-foo_bar-volume-backup.tar.gz.tmp", "-C", "/", "foo/data", "foo/config",
                "bar/log"] == tar_cmd

    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    def test_create_tar_cmd_default_bz2(self, host):
        with patch("docker_volume_backup.container.backup.Backup._determine_compression_method",
                   return_value=("-j", ".bz2")):
            container = MockContainer()
            backup_dir = MockBackupDir()
            backup = Backup(container=container, backup_dir=backup_dir)
            tar_cmd = backup._create_tar_cmd()
            assert ["tar", "c", "-j", "-f", f"/backup/groot-foo_bar-volume-backup.tar.bz2.tmp", "-C", "/", "foo/data", "foo/config",
                    "bar/log"] == tar_cmd

    @patch("docker_volume_backup.container.backup.os.getenv", return_value="GZIP")
    def test_determine_compression_method_gz(self, env):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        assert ("-z", ".gz") == backup._determine_compression_method()

    @patch("docker_volume_backup.container.backup.os.getenv", return_value="BZIP2")
    def test_determine_compression_method_bz2(self, env):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        assert ("-j", ".bz2") == backup._determine_compression_method()

    @patch("docker_volume_backup.container.backup.os.getenv", return_value="")
    def test_determine_compression_method_default(self, env):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        assert ("-z", ".gz") == backup._determine_compression_method()

    @patch.dict("docker_volume_backup.container.backup.os.environ",
                {"BACKUP_FILE_OWNER": "9876", "BACKUP_FILE_GROUP": "9876", "BACKUP_FILE_PERMS": "777"})
    def test_should_change_filesettings_true_true(self):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual((True, True), backup.should_change_filesettings())

    @patch.dict("docker_volume_backup.container.backup.os.environ",
                {"BACKUP_FILE_GROUP": "9876"})
    def test_should_change_filesettings_true_false(self):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual((True, False), backup.should_change_filesettings())

    @patch.dict("docker_volume_backup.container.backup.os.environ",
                {"BACKUP_FILE_OWNER": "", "BACKUP_FILE_PERMS": "741"})
    def test_should_change_filesettings_false_true(self):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual((False, True), backup.should_change_filesettings())

    def test_should_change_filesettings_false_false(self):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual((False, False), backup.should_change_filesettings())

    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    def test_get_backup_filepath(self, host):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual("/backup/groot-foo_bar-volume-backup.tar.gz", backup._get_backup_filepath())

    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    def test_get_backup_filename(self, host):
        with patch("docker_volume_backup.container.backup.Backup._determine_compression_method",
                   return_value=("-j", ".bz2")):
            container = MockContainer()
            backup_dir = MockBackupDir()
            backup = Backup(container=container, backup_dir=backup_dir)
            self.assertEqual("groot-foo_bar-volume-backup.tar.bz2", backup._get_backup_filename())

    @patch("docker_volume_backup.container.backup.os.path.getsize", return_value=987654321)
    def test_get_backup_file_size(self, filesize):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual(987654321, backup._get_backup_file_size())

    @patch("docker_volume_backup.container.backup.datetime")
    def test_should_refresh_image_true_on_default_day(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2026, 3, 1)
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertTrue(backup._should_refresh_image())

    @patch("docker_volume_backup.container.backup.datetime")
    def test_should_refresh_image_false_on_other_days(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2026, 3, 15)
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertFalse(backup._should_refresh_image())

    @patch.dict("docker_volume_backup.container.backup.os.environ", {"IMAGE_REFRESH_DAY": "15"})
    @patch("docker_volume_backup.container.backup.datetime")
    def test_should_refresh_image_true_on_configured_day(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2026, 3, 15)
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertTrue(backup._should_refresh_image())

    @patch.dict("docker_volume_backup.container.backup.os.environ", {"IMAGE_REFRESH_DAY": "15"})
    def test_get_image_refresh_day_configured(self):
        self.assertEqual(15, Backup._get_image_refresh_day())

    @patch.dict("docker_volume_backup.container.backup.os.environ", {}, clear=True)
    def test_get_image_refresh_day_default_when_unset(self):
        self.assertEqual(1, Backup._get_image_refresh_day())

    @patch.dict("docker_volume_backup.container.backup.os.environ", {"IMAGE_REFRESH_DAY": "foo"})
    def test_get_image_refresh_day_falls_back_on_invalid_value(self):
        self.assertEqual(1, Backup._get_image_refresh_day())

    @patch.dict("docker_volume_backup.container.backup.os.environ", {"IMAGE_REFRESH_DAY": "45"})
    def test_get_image_refresh_day_falls_back_on_out_of_range_value(self):
        self.assertEqual(1, Backup._get_image_refresh_day())

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=True)
    @patch("docker_volume_backup.container.backup.docker.run", return_value="Everything is allright")
    def test_exec_docker_run_pulls_on_refresh_day(self, docker_run, should_refresh):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        backup._exec_docker_run(["chown", "1000", backup.backup_file])
        self.assertEqual("always", docker_run.call_args.kwargs["pull"])

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.docker.run", return_value="Everything is allright")
    def test_exec_docker_run_skips_pull_on_other_days(self, docker_run, should_refresh):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        backup._exec_docker_run(["chown", "1000", backup.backup_file])
        self.assertEqual("missing", docker_run.call_args.kwargs["pull"])

    @patch("docker_volume_backup.container.backup.os.path.getsize", side_effect=FileNotFoundError("no such file"))
    def test_get_backup_file_size_missing_file_is_logged(self, filesize):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        with self.assertLogs("docker_volume_backup.container.backup", level="ERROR") as log:
            with self.assertRaises(FileNotFoundError):
                backup._get_backup_file_size()

        self.assertIn("Not able to determine file size. Backup file not found: /foo/backup/", log.output[0])
