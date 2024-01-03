import datetime
import os
from unittest import TestCase
from unittest.mock import patch

import docker.errors
from dotenv import load_dotenv

from util.accessor import BackupDir, LocalHost, calc_duration, EnvSettings


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


class TestAccessorEnvSettings(TestCase):

    def tearDown(self):
        env_settings = ["CHAT_ALERTING", "CHAT_SERVICE", "SLACK_CHANNEL_ID", "SLACK_AUTH_TOKEN", "MQTT_ALERTING",
                        "MQTT_BROKER", "MQTT_TOPIC"]
        for env_setting in env_settings:
            try:
                del os.environ[env_setting]
            except KeyError as err:
                pass

    def test_validate_env_settings(self):
        load_dotenv("fixtures/env_files/.env_ok")
        self.assertIsNone(EnvSettings().validate(), "Validate correct env settings failed")

    def test_validate_env_settings_chat_error(self):
        load_dotenv("fixtures/env_files/.env_chat_error")
        with self.assertRaises(ValueError) as err:
            EnvSettings().validate()

        self.assertEqual("CHAT_ALERTING enabled but CHAT_SERVICE not correct. Check .env config.", str(err.exception),
                         "Chat settings error not raised")

    def test_validate_env_settings_slack_error(self):
        load_dotenv("fixtures/env_files/.env_chat_slack_error")
        with self.assertRaises(ValueError) as err:
            EnvSettings().validate()

        self.assertEqual("CHAT_SERVICE=SLACK but SLACK_CHANNEL_ID / SLACK_AUTH_TOKEN missing. Check .env config.",
                         str(err.exception), "Slack settings error not raised")

    def test_validate_env_settings_mqtt_error(self):
        load_dotenv("fixtures/env_files/.env_mqtt_error")
        with self.assertRaises(ValueError) as err:
            EnvSettings().validate()

        self.assertEqual("MQTT_ALERTING enabled but MQTT config not correct. Check .env config.",
                         str(err.exception), "MQTT settings error not raised")


class TestAccessorLocalhost(TestCase):
    def test_get_hostname(self):
        hostname = LocalHost.get_hostname()
        self.assertTrue(hostname.islower())

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


def test_calc_duration():
    assert calc_duration(1924945200, 1924952402) == datetime.timedelta(seconds=7202)
    assert str(calc_duration(1924945200, 1924952402)) == "2:00:02"
