from unittest import TestCase
from unittest.mock import patch

import docker.errors

from util.accessor import BackupDir, LocalHost


class TestAccessorBackupDir(TestCase):
    def test_backup_dir_success(self):
        backup_dir = BackupDir("/Foo/")
        self.assertEqual(backup_dir.path, "/Foo/", "Invalid container directory")

    @patch("src.util.accessor.os.getenv", return_value="")
    def test_backup_dir_path_not_set(self, dir):
        with self.assertRaises(ValueError):
            BackupDir("")

    @patch("src.util.accessor.os.path.isdir", return_value=True)
    def test_backup_dir_exists(self, mock_dir):
        backup_dir = BackupDir("/Foo")
        self.assertIsNone(backup_dir.create(), "Directory not found, but should")

    @patch("src.util.accessor.os.path.isdir", return_value=False)
    @patch("src.util.accessor.os.makedirs", return_value=None)
    def test_backup_dir_created(self, mock_dir, mock_makedirs):
        backup_dir = BackupDir("/Foo")
        self.assertIsNone(backup_dir.create(), "Directory not found, but should")

    @patch("src.util.accessor.os.path.isdir", return_value=False)
    @patch("src.util.accessor.os.makedirs", side_effect=FileExistsError("Directory already exists"))
    def test_backup_dir_error(self, mock_dir, mock_makedir):
        backup_dir = BackupDir("/Foo")
        with self.assertLogs("util.accessor", level="INFO") as log:
            backup_dir.create()
            self.assertEqual(
                ["INFO:util.accessor:Backup directory '/Foo' exists. Directory already exists"],
                log.output)


class TestAccessorLocalhost(TestCase):
    def test_get_hostname(self):
        hostname = LocalHost.get_hostname()
        self.assertTrue(hostname.islower())

    def test_get_hostname_upper(self):
        hostname = LocalHost.get_hostname_upper()
        self.assertTrue(hostname.isupper())

    @patch("src.util.accessor.docker.from_env", side_effect=ConnectionError(
        "('Connection aborted.', ConnectionRefusedError(111, 'Connection refused')"))
    def test_is_docker_daemon_running_exception(self, client):
        with self.assertLogs("util.accessor", level="ERROR") as log:
            self.assertFalse(LocalHost.is_docker_daemon_running())
            self.assertEqual([
                f"ERROR:util.accessor:Error while checking Docker daemon on {LocalHost.get_hostname()}, "
                "('Connection aborted.', ConnectionRefusedError(111, 'Connection refused')"],
                log.output)

    @patch("src.util.accessor.docker.from_env", return_value="<docker.client.Client object at 0xffff8713be90>")
    def test_is_docker_daemon_running_docker_exception(self, client):
        with self.assertLogs("util.accessor", level="ERROR") as log:
            LocalHost.is_docker_daemon_running()
            self.assertRaises(docker.errors.DockerException)


    @patch("src.util.accessor.docker.api.daemon.DaemonApiMixin.ping", return_value="OK")
    def test_is_docker_daemon_running(self, ping):
        self.assertTrue(LocalHost.is_docker_daemon_running())
