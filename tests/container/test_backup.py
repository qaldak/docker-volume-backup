import unittest
from unittest import TestCase
from unittest.mock import patch

from python_on_whales import DockerException

from container.backup import Backup


class MockContainer(TestCase):
    @unittest.expectedFailure
    def __init__(self) -> None:
        super().__init__()
        self.name = "foo_bar"
        self.docker_volumes = ["/foo/data", "/foo/config"]
        self.docker_bindings = ["/bar/log"]
        self.has_docker_volume = True
        self.has_docker_bindings = True


class MockBackupDir(TestCase):
    @unittest.expectedFailure
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

    @patch("src.container.backup.docker.run", side_effect=DockerException(command_launched=[""], return_code=115))
    def test_run_backup_docker_exception(self, error):
        backup_dir = MockBackupDir()
        container = MockContainer()
        with self.assertRaises(DockerException) as err:
            Backup(container=container, backup_dir=backup_dir).run_backup()
        self.assertEqual(115, err.exception.return_code)

    @patch("src.container.backup.os.path.getsize", return_value=987654321)
    @patch("src.container.backup.LocalHost.get_hostname", return_value="groot")
    @patch("src.container.backup.docker.run", return_value="Everything is allright")
    def test_run_backup_successful(self, tmp, hostname, filesize):
        backup_dir = MockBackupDir()
        container = MockContainer()
        with self.assertLogs("container.backup", level="INFO") as log:
            Backup(container=container, backup_dir=backup_dir).run_backup()
            self.assertEqual([
                "INFO:container.backup:Execute Volume backup for container 'foo_bar'. tar "
                "command: ['tar', 'c', '-z', '-f', "
                "'/backup/groot-foo_bar-volume-backup.tar.gz', '/foo/data', '/foo/config', "
                "'/bar/log']",
                "INFO:container.backup:Volume backup for container 'foo_bar' successful. "
                'Duration: 0:00:00, Backup size: 987654321'],
                log.output)

    @patch("src.container.backup.LocalHost.get_hostname", return_value="groot")
    def test_create_tar_cmd_default(self, host):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        tar_cmd = backup._create_tar_cmd()
        assert ["tar", "c", "-z", "-f", f"/backup/groot-foo_bar-volume-backup.tar.gz", "/foo/data", "/foo/config",
                "/bar/log"] == tar_cmd

    @patch("src.container.backup.LocalHost.get_hostname", return_value="groot")
    def test_create_tar_cmd_default_bz2(self, host):
        with patch("container.backup.Backup._determine_compression_method", return_value=("-j", ".bz2")):
            container = MockContainer()
            backup_dir = MockBackupDir()
            backup = Backup(container=container, backup_dir=backup_dir)
            tar_cmd = backup._create_tar_cmd()
            assert ["tar", "c", "-j", "-f", f"/backup/groot-foo_bar-volume-backup.tar.bz2", "/foo/data", "/foo/config",
                    "/bar/log"] == tar_cmd

    @patch("src.container.backup.os.getenv", return_value="GZIP")
    def test_determine_compression_method_gz(self, env):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        assert ("-z", ".gz") == backup._determine_compression_method()

    @patch("src.container.backup.os.getenv", return_value="BZIP2")
    def test_determine_compression_method_bz2(self, env):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        assert ("-j", ".bz2") == backup._determine_compression_method()

    @patch("src.container.backup.os.getenv", return_value="")
    def test_determine_compression_method_default(self, env):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        assert ("-z", ".gz") == backup._determine_compression_method()

    @patch.dict("src.container.backup.os.environ",
                {"BACKUP_FILE_OWNER": "9876", "BACKUP_FILE_GROUP": "9876", "BACKUP_FILE_PERMS": "777"})
    def test_should_change_filesettings_true_true(self):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual((True, True), backup.should_change_filesettings())

    @patch.dict("src.container.backup.os.environ",
                {"BACKUP_FILE_GROUP": "9876"})
    def test_should_change_filesettings_true_false(self):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual((True, False), backup.should_change_filesettings())

    @patch.dict("src.container.backup.os.environ",
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

    @patch("src.container.backup.LocalHost.get_hostname", return_value="groot")
    def test_get_backup_filepath(self, host):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual("/backup/groot-foo_bar-volume-backup.tar.gz", backup._get_backup_filepath())

    @patch("src.container.backup.LocalHost.get_hostname", return_value="groot")
    def test_get_backup_filename(self, host):
        with patch("container.backup.Backup._determine_compression_method", return_value=("-j", ".bz2")):
            container = MockContainer()
            backup_dir = MockBackupDir()
            backup = Backup(container=container, backup_dir=backup_dir)
            self.assertEqual("groot-foo_bar-volume-backup.tar.bz2", backup._get_backup_filename())

    @patch("src.container.backup.os.path.getsize", return_value=987654321)
    def test_get_backup_file_size(self, filesize):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual(987654321, backup._get_backup_file_size())
