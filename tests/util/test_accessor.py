import datetime
import os
import stat
import tempfile
from unittest import TestCase
from unittest.mock import patch

import docker.errors
from dotenv import load_dotenv

from docker_volume_backup.util.accessor import BackupDir, LocalHost, calc_duration, EnvSettings, parse_file_mode


class TestAccessorBackupDir(TestCase):
    def test_backup_dir_success(self):
        backup_dir = BackupDir("/Foo/")
        self.assertEqual(backup_dir.path, "/Foo/", "Invalid container directory")

    @patch("docker_volume_backup.util.accessor.os.getenv", return_value="")
    def test_backup_dir_path_not_set(self, dir):
        with self.assertRaises(ValueError):
            BackupDir("")

    @patch("docker_volume_backup.util.accessor.os.path.isdir", return_value=True)
    def test_backup_dir_exists(self, mock_dir):
        backup_dir = BackupDir("/Foo")
        self.assertIsNone(backup_dir.create(), "Directory not found, but should")

    @patch("docker_volume_backup.util.accessor.os.chmod")
    @patch("docker_volume_backup.util.accessor.os.path.isdir", return_value=False)
    @patch("docker_volume_backup.util.accessor.os.makedirs", return_value=None)
    def test_backup_dir_created(self, mock_dir, mock_makedirs, mock_chmod):
        backup_dir = BackupDir("/Foo")
        self.assertIsNone(backup_dir.create(), "Directory not found, but should")

    @patch.dict("docker_volume_backup.util.accessor.os.environ", {}, clear=True)
    def test_backup_dir_created_with_default_permissions(self):
        previous_umask = os.umask(0)  # permissions must not depend on the umask
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = os.path.join(directory, "backup")
                BackupDir(path).create()
                self.assertEqual(0o750, stat.S_IMODE(os.stat(path).st_mode))
        finally:
            os.umask(previous_umask)

    @patch.dict("docker_volume_backup.util.accessor.os.environ", {"BACKUP_DIR_PERMS": "700"}, clear=True)
    def test_backup_dir_created_with_configured_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "backup")
            BackupDir(path).create()
            self.assertEqual(0o700, stat.S_IMODE(os.stat(path).st_mode))

    @patch.dict("docker_volume_backup.util.accessor.os.environ", {"BACKUP_DIR_PERMS": "700"}, clear=True)
    def test_existing_backup_dir_permissions_are_not_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o755)
            BackupDir(directory).create()
            self.assertEqual(0o755, stat.S_IMODE(os.stat(directory).st_mode))

    @patch("docker_volume_backup.util.accessor.os.path.isdir", return_value=False)
    @patch("docker_volume_backup.util.accessor.os.makedirs",
           side_effect=FileExistsError("Directory already exists"))
    def test_backup_dir_error(self, mock_dir, mock_makedir):
        backup_dir = BackupDir("/Foo")
        with self.assertLogs("docker_volume_backup.util.accessor", level="INFO") as log:
            backup_dir.create()
            self.assertEqual(
                ["INFO:docker_volume_backup.util.accessor:Backup directory '/Foo' exists. Directory already exists"],
                log.output)


class TestAccessorEnvSettings(TestCase):

    def tearDown(self):
        env_settings = ["CHAT_ALERTING", "CHAT_SERVICE", "SLACK_CHANNEL_ID", "SLACK_AUTH_TOKEN", "MQTT_ALERTING",
                        "MQTT_BROKER", "MQTT_PORT", "MQTT_TOPIC"]
        for env_setting in env_settings:
            try:
                del os.environ[env_setting]
            except KeyError as err:
                pass

    def test_validate_env_settings(self):
        load_dotenv("tests/fixtures/env_files/.env_ok")
        self.assertIsNone(EnvSettings().validate(), "Validate correct env settings failed")

    def test_validate_env_settings_chat_error(self):
        load_dotenv("tests/fixtures/env_files/.env_chat_error")
        with self.assertRaises(ValueError) as err:
            EnvSettings().validate()

        self.assertEqual("CHAT_ALERTING enabled but CHAT_SERVICE not correct. Check .env config.", str(err.exception),
                         "Chat settings error not raised")

    def test_validate_env_settings_slack_error(self):
        load_dotenv("tests/fixtures/env_files/.env_chat_slack_error")
        with self.assertRaises(ValueError) as err:
            EnvSettings().validate()

        self.assertEqual("CHAT_SERVICE=SLACK but SLACK_CHANNEL_ID / SLACK_AUTH_TOKEN missing. Check .env config.",
                         str(err.exception), "Slack settings error not raised")

    def test_validate_env_settings_mqtt_error(self):
        load_dotenv("tests/fixtures/env_files/.env_mqtt_error")
        with self.assertRaises(ValueError) as err:
            EnvSettings().validate()

        self.assertEqual("MQTT_ALERTING enabled but MQTT config not correct. Check .env config.",
                         str(err.exception), "MQTT settings error not raised")


class TestAccessorLocalhost(TestCase):
    def test_get_hostname(self):
        hostname = LocalHost.get_hostname()
        self.assertTrue(hostname.islower())

    @patch("docker_volume_backup.util.accessor.docker.from_env", side_effect=ConnectionError(
        "('Connection aborted.', ConnectionRefusedError(111, 'Connection refused')"))
    def test_is_docker_daemon_running_exception(self, client):
        with self.assertLogs("docker_volume_backup.util.accessor", level="ERROR") as log:
            self.assertFalse(LocalHost.is_docker_daemon_running())
            self.assertEqual([
                f"ERROR:docker_volume_backup.util.accessor:Error while checking Docker daemon on {LocalHost.get_hostname()}, "
                "('Connection aborted.', ConnectionRefusedError(111, 'Connection refused')"],
                log.output)

    @patch("docker_volume_backup.util.accessor.docker.from_env",
           return_value="<docker.client.Client object at 0xffff8713be90>")
    def test_is_docker_daemon_running_docker_exception(self, client):
        with self.assertLogs("docker_volume_backup.util.accessor", level="ERROR") as log:
            LocalHost.is_docker_daemon_running()
            self.assertRaises(docker.errors.DockerException)

    @patch("docker_volume_backup.util.accessor.docker.api.daemon.DaemonApiMixin.ping", return_value="OK")
    def test_is_docker_daemon_running(self, ping):
        self.assertTrue(LocalHost.is_docker_daemon_running())


def test_calc_duration():
    assert calc_duration(1924945200, 1924952402) == datetime.timedelta(seconds=7202)
    assert str(calc_duration(1924945200, 1924952402)) == "2:00:02"


class TestParseFileMode(TestCase):

    def test_valid_modes(self):
        self.assertEqual(0o640, parse_file_mode("640", 0o600, "FOO"))
        self.assertEqual(0o2750, parse_file_mode("2750", 0o600, "FOO"))
        self.assertEqual(0o741, parse_file_mode(" 741 ", 0o600, "FOO"))

    def test_undefined_or_empty_uses_default_without_warning(self):
        self.assertEqual(0o640, parse_file_mode(None, 0o640, "FOO"))
        self.assertEqual(0o640, parse_file_mode("", 0o640, "FOO"))

    def test_invalid_modes_use_default_with_warning(self):
        for value in ("rwx", "999", "-1", "0o640", "12345", "64 0"):
            with self.subTest(value=value):
                with self.assertLogs("docker_volume_backup.util.accessor", level="WARNING") as log:
                    self.assertEqual(0o640, parse_file_mode(value, 0o640, "FOO"))
                self.assertIn("FOO not defined properly", log.output[0])
