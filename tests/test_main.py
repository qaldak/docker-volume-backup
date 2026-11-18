import os
import subprocess
import sys
import tempfile
from unittest import TestCase
from unittest.mock import MagicMock, patch

from python_on_whales import DockerException

from docker_volume_backup import main
from docker_volume_backup.util import cfg


def _reset_cfg():
    cfg.hasError = False
    cfg.errorMsg = ""
    cfg.hasWarning = False
    cfg.warningMsg = ""


class TestCreateBackup(TestCase):

    def setUp(self):
        _reset_cfg()
        self.container = MagicMock()
        self.container.name = "foo_bar"
        self.container.exists.return_value = True
        self.container.is_volume_available.return_value = True

        self.backup = MagicMock()
        self.backup.should_change_filesettings.return_value = (False, False)

        patches = [
            patch.object(main.LocalHost, "is_docker_daemon_running", return_value=True),
            patch.object(main, "BackupDir"),
            patch.object(main, "Backup", return_value=self.backup),
            patch.object(main, "Dispatcher"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.dispatcher = main.Dispatcher.return_value

    def tearDown(self):
        _reset_cfg()

    def test_success_without_restart_does_not_touch_container(self):
        self.assertTrue(main.create_backup(self.container, "/backup", restart=False))

        self.container.stop.assert_not_called()
        self.container.start.assert_not_called()
        self.assertFalse(cfg.hasError)
        self.dispatcher.notify_chat_receiver.assert_called_once()
        self.dispatcher.notify_mqtt_receiver.assert_called_once()

    def test_success_with_restart_stops_and_starts_container(self):
        self.assertTrue(main.create_backup(self.container, "/backup", restart=True))

        self.container.stop.assert_called_once()
        self.container.start.assert_called_once()
        self.assertFalse(cfg.hasError)

    def test_failed_backup_with_restart_still_restarts_container(self):
        self.backup.run_backup.side_effect = RuntimeError("tar failed")

        with self.assertLogs("docker_volume_backup.main", level="ERROR"):
            self.assertFalse(main.create_backup(self.container, "/backup", restart=True))

        self.container.stop.assert_called_once()
        self.container.start.assert_called_once()
        self.assertTrue(cfg.hasError)
        self.assertIn("tar failed", str(cfg.errorMsg))
        self.dispatcher.notify_chat_receiver.assert_called_once()

    def test_failed_chown_with_restart_still_restarts_container(self):
        self.backup.should_change_filesettings.return_value = (True, False)
        self.backup.change_file_ownership.side_effect = RuntimeError("chown failed")

        with self.assertLogs("docker_volume_backup.main", level="ERROR"):
            self.assertFalse(main.create_backup(self.container, "/backup", restart=True))

        self.container.start.assert_called_once()

    def test_failing_stop_still_tries_to_start_container(self):
        self.container.stop.side_effect = RuntimeError("stop failed")

        with self.assertLogs("docker_volume_backup.main", level="ERROR"):
            self.assertFalse(main.create_backup(self.container, "/backup", restart=True))

        self.container.start.assert_called_once()
        self.backup.run_backup.assert_not_called()

    def test_failure_before_stop_does_not_start_container(self):
        self.container.exists.return_value = False

        with self.assertLogs("docker_volume_backup.main", level="ERROR"):
            self.assertFalse(main.create_backup(self.container, "/backup", restart=True))

        self.container.stop.assert_not_called()
        self.container.start.assert_not_called()

    def test_failing_restart_after_successful_backup_is_reported(self):
        self.container.start.side_effect = RuntimeError("not (re)started properly")

        with self.assertLogs("docker_volume_backup.main", level="ERROR"):
            self.assertFalse(main.create_backup(self.container, "/backup", restart=True))

        self.assertTrue(cfg.hasError)
        self.assertIn("not (re)started properly", str(cfg.errorMsg))
        self.dispatcher.notify_chat_receiver.assert_called_once()

    def test_failing_restart_keeps_original_backup_error(self):
        self.backup.run_backup.side_effect = RuntimeError("tar failed")
        self.container.start.side_effect = RuntimeError("not (re)started properly")

        with self.assertLogs("docker_volume_backup.main", level="ERROR"):
            self.assertFalse(main.create_backup(self.container, "/backup", restart=True))

        self.assertIn("tar failed", str(cfg.errorMsg))
        self.assertIn("not (re)started properly", str(cfg.errorMsg))

    def test_failing_notification_does_not_change_backup_result(self):
        def notification_failed():
            cfg.hasError = True  # e.g. Slack.post_message marks failed posting as error

        self.dispatcher.notify_chat_receiver.side_effect = notification_failed

        self.assertTrue(main.create_backup(self.container, "/backup", restart=False))


class TestCreateBackupMissingBackupFile(TestCase):
    """
    The real Backup class is used: if the backup file is not found on the host after the backup, the error has to
    arrive in cfg (result, exit code and notifications depend on it)
    """

    def setUp(self):
        _reset_cfg()
        self.addCleanup(_reset_cfg)

        self.container = MagicMock()
        self.container.name = "foo_bar"
        self.container.exists.return_value = True
        self.container.is_volume_available.return_value = True
        self.container.docker_volumes = ["/foo/data"]
        self.container.docker_bindings = []
        self.container.has_docker_volume = True
        self.container.has_docker_bindings = False

        backup_dir = MagicMock()
        backup_dir.path = "/nonexistent_backup_dir"

        # state that the notifications see
        self.notified = {}

        def notify():
            self.notified.update(has_error=cfg.hasError, error_msg=cfg.errorMsg)

        patches = [
            patch.object(main.LocalHost, "is_docker_daemon_running", return_value=True),
            patch.object(main, "BackupDir", return_value=backup_dir),
            patch.object(main, "Dispatcher"),
            patch("docker_volume_backup.container.backup.docker.run", return_value=""),
            patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        main.Dispatcher.return_value.notify_chat_receiver.side_effect = notify

    def test_missing_backup_file_sets_error_in_cfg(self):
        with self.assertLogs("docker_volume_backup", level="ERROR"):
            result = main.create_backup(self.container, "/backup", restart=False)

        self.assertFalse(result)
        self.assertTrue(cfg.hasError)
        self.assertIsInstance(cfg.errorMsg, FileNotFoundError)
        self.assertIn("/nonexistent_backup_dir/", str(cfg.errorMsg))
        self.assertIn("No such file or directory", str(cfg.errorMsg))

    def test_missing_backup_file_error_is_known_when_notifications_are_sent(self):
        with self.assertLogs("docker_volume_backup", level="ERROR"):
            main.create_backup(self.container, "/backup", restart=False)

        self.assertTrue(self.notified["has_error"])
        self.assertIn("/nonexistent_backup_dir/", str(self.notified["error_msg"]))


class TestVerificationFailureIsReported(TestCase):
    """
    Real Backup, Dispatcher and Builder, only the transports (docker, Slack, MQTT) are replaced: a backup file that
    fails the verification has to end up as error in the result, the exit code, the chat message and the MQTT message.
    """

    ENV = {"CHAT_ALERTING": "ON_FAILURE", "CHAT_SERVICE": "SLACK", "MQTT_ALERTING": "ON_FAILURE",
           "MQTT_TOPIC": "backup/{CONTAINER}", "SLACK_AUTH_TOKEN": "x", "SLACK_CHANNEL_ID": "y"}

    def setUp(self):
        _reset_cfg()
        self.addCleanup(_reset_cfg)

        self.container = MagicMock()
        self.container.name = "foo_bar"
        self.container.exists.return_value = True
        self.container.is_volume_available.return_value = True
        self.container.docker_volumes = ["/foo/data"]
        self.container.docker_bindings = []
        self.container.has_docker_volume = True
        self.container.has_docker_bindings = False

        backup_dir = MagicMock()
        backup_dir.path = "/backup_dir"

        def docker_run(image, cmd, **kwargs):
            if cmd[:2] == ["sh", "-c"] and "tar -t" in cmd[2]:
                raise DockerException(command_launched=cmd, return_code=1)
            return ""

        self.docker_run = patch("docker_volume_backup.container.backup.docker.run", side_effect=docker_run).start()
        patches = [
            patch.dict(os.environ, self.ENV, clear=True),
            patch.object(main.LocalHost, "is_docker_daemon_running", return_value=True),
            patch.object(main, "BackupDir", return_value=backup_dir),
            patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False),
            patch("docker_volume_backup.notification.dispatcher.Slack"),
            patch("docker_volume_backup.notification.dispatcher.MQTT"),
        ]
        for p in patches:
            p.start()
        self.addCleanup(patch.stopall)
        self.slack = sys.modules["docker_volume_backup.notification.dispatcher"].Slack.return_value
        self.mqtt_class = sys.modules["docker_volume_backup.notification.dispatcher"].MQTT

    def test_failed_verification_is_error_and_is_sent_to_chat_and_mqtt(self):
        with self.assertLogs("docker_volume_backup", level="ERROR"):
            result = main.create_backup(self.container, "/backup", restart=False)

        self.assertFalse(result)

        chat_msg = self.slack.post_message.call_args.args[0]
        self.assertIn("An error occurred while backing up container 'foo_bar'", chat_msg)
        self.assertIn("verification failed", chat_msg)
        self.assertIn("The last backup was not replaced", chat_msg)

        topic, mqtt_msg = self.mqtt_class.call_args.args
        self.assertEqual("backup/foo_bar", topic)
        self.assertTrue(mqtt_msg["hasError"])
        self.assertIn("verification failed", mqtt_msg["msg"])
        self.mqtt_class.return_value.send_msg.assert_called_once()

    def test_failed_verification_removes_tmp_file_and_does_not_replace_backup(self):
        with self.assertLogs("docker_volume_backup", level="ERROR"):
            main.create_backup(self.container, "/backup", restart=False)

        commands = [call.args[1] for call in self.docker_run.call_args_list]
        names = [cmd[4] if cmd[0] == "sh" and cmd[3] == "sh" and cmd[2].startswith("umask") else
                 ("verify" if cmd[0] == "sh" else cmd[0]) for cmd in commands]
        self.assertEqual(["tar", "verify", "rm"], names)

    def test_failed_verification_with_restart_still_starts_container(self):
        with self.assertLogs("docker_volume_backup", level="ERROR"):
            main.create_backup(self.container, "/backup", restart=True)

        self.container.stop.assert_called_once()
        self.container.start.assert_called_once()


class TestNotificationErrors(TestCase):
    """a failing notification must neither stop the other one nor change the result of the backup"""

    def setUp(self):
        _reset_cfg()
        self.addCleanup(_reset_cfg)

        self.container = MagicMock()
        self.container.name = "foo_bar"
        self.container.exists.return_value = True
        self.container.is_volume_available.return_value = True

        self.backup = MagicMock()
        self.backup.should_change_filesettings.return_value = (False, False)

        patches = [
            patch.object(main.LocalHost, "is_docker_daemon_running", return_value=True),
            patch.object(main, "BackupDir"),
            patch.object(main, "Backup", return_value=self.backup),
            patch.object(main, "Dispatcher"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.dispatcher = main.Dispatcher.return_value

    def test_failing_chat_notification_does_not_skip_mqtt(self):
        self.dispatcher.notify_chat_receiver.side_effect = ConnectionError("Slack not reachable")

        with self.assertLogs("docker_volume_backup.main", level="ERROR") as log:
            result = main.create_backup(self.container, "/backup", restart=False)

        self.assertTrue(result)
        self.dispatcher.notify_mqtt_receiver.assert_called_once()
        self.assertIn("Notification failed", log.output[0])
        self.assertIn("Slack not reachable", log.output[0])

    def test_failing_mqtt_notification_is_logged_and_does_not_change_result(self):
        self.dispatcher.notify_mqtt_receiver.side_effect = ValueError("MQTT_TOPIC undefined in .env file")

        with self.assertLogs("docker_volume_backup.main", level="ERROR") as log:
            result = main.create_backup(self.container, "/backup", restart=False)

        self.assertTrue(result)
        self.dispatcher.notify_chat_receiver.assert_called_once()
        self.assertIn("MQTT_TOPIC undefined", log.output[0])

    def test_both_notifications_failing_keeps_failed_backup_result(self):
        self.backup.run_backup.side_effect = RuntimeError("tar failed")
        self.dispatcher.notify_chat_receiver.side_effect = ConnectionError("down")
        self.dispatcher.notify_mqtt_receiver.side_effect = ConnectionError("down")

        with self.assertLogs("docker_volume_backup.main", level="ERROR"):
            result = main.create_backup(self.container, "/backup", restart=False)

        self.assertFalse(result)
        self.assertTrue(cfg.hasError)

    def test_notification_setup_failing_does_not_raise(self):
        main.Dispatcher.side_effect = RuntimeError("invalid alerting")

        with self.assertLogs("docker_volume_backup.main", level="ERROR") as log:
            self.assertTrue(main.create_backup(self.container, "/backup", restart=False))

        self.assertIn("Notifications could not be prepared", log.output[0])

    def test_container_is_restarted_even_if_notification_fails(self):
        self.dispatcher.notify_chat_receiver.side_effect = ConnectionError("down")

        with self.assertLogs("docker_volume_backup.main", level="ERROR"):
            main.create_backup(self.container, "/backup", restart=True)

        self.container.start.assert_called_once()


class TestMain(TestCase):

    def setUp(self):
        _reset_cfg()
        self.args = MagicMock(backup=True, restore=False, container="foo_bar", path=None, restart=False)
        patcher = patch.object(main, "Container")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exit_code_is_zero_on_success(self):
        with patch.object(main, "create_backup", return_value=True):
            self.assertEqual(0, main.main(self.args))

    def test_exit_code_is_one_if_backup_failed(self):
        with patch.object(main, "create_backup", return_value=False):
            self.assertEqual(1, main.main(self.args))

    def test_backup_receives_container_path_and_restart(self):
        with patch.object(main, "create_backup", return_value=True) as create_backup:
            main.main(self.args)

        create_backup.assert_called_once_with(main.Container.return_value, None, False)
        main.Container.assert_called_once_with("foo_bar")

    def test_restore_is_run_for_restore_args(self):
        args = MagicMock(backup=False, restore=True, dockervolume="foo_data", targetpath="/foo", backupfile="b.tar.gz",
                         sourcepath=None, yes=False)

        with patch.object(main, "restore_backup", return_value=True) as restore_backup, \
                patch.object(main, "create_backup") as create_backup:
            self.assertEqual(0, main.main(args))

        restore_backup.assert_called_once_with("foo_data", "/foo", "b.tar.gz", None, False)
        create_backup.assert_not_called()

    def test_exit_code_is_one_if_restored_volume_is_incomplete(self):
        args = MagicMock(backup=False, restore=True, dockervolume="foo_data", targetpath="/foo", backupfile="b.tar.gz",
                         sourcepath=None, yes=False)

        with patch.object(main, "restore_backup", return_value=False):
            self.assertEqual(1, main.main(args))


class TestRestoreBackup(TestCase):

    def setUp(self):
        patches = [
            patch.object(main.os.path, "exists", return_value=True),
            patch.object(main, "Recovery"),
            patch.object(main, "Volume"),
            patch("builtins.print"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        self.recovery = main.Recovery.return_value
        self.recovery.check_recovery.return_value = True
        self.recovery.volume_has_content.return_value = False

        self.volume = main.Volume.return_value
        self.volume.exists.return_value = True
        self.volume.containers.side_effect = lambda running_only=False: []

    def _containers(self, running=(), stopped=()):
        self.volume.containers.side_effect = \
            lambda running_only=False: list(running) if running_only else list(running) + list(stopped)

    def _stdin(self, tty):
        patcher = patch.object(main.sys, "stdin", MagicMock(isatty=MagicMock(return_value=tty)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_source_path_is_checked_before_docker_volume_is_touched(self):
        self.recovery.resolve_source_path.side_effect = ValueError("contains 2 paths")

        with self.assertRaises(ValueError):
            main.restore_backup("foo_data", "/foo", "b.tar.gz")

        main.Volume.assert_not_called()
        self.recovery.restore_volume_backup.assert_not_called()

    def test_restore_passes_source_path_and_works_without_it(self):
        main.restore_backup("foo_data", "/foo", "b.tar.gz")
        main.Recovery.assert_called_with(docker_volume="foo_data", target_path="/foo", backup_file="b.tar.gz",
                                         source_path=None)

        main.restore_backup("foo_data", "/foo", "b.tar.gz", "/foo/data")
        main.Recovery.assert_called_with(docker_volume="foo_data", target_path="/foo", backup_file="b.tar.gz",
                                         source_path="/foo/data")
        self.assertEqual(2, self.recovery.restore_volume_backup.call_count)

    def test_restore_result_is_result_of_check(self):
        self.recovery.check_recovery.return_value = True
        self.assertTrue(main.restore_backup("foo_data", "/foo", "b.tar.gz"))

        self.recovery.check_recovery.return_value = False
        self.assertFalse(main.restore_backup("foo_data", "/foo", "b.tar.gz"))

    def test_new_volume_is_created_and_restored_without_content_check(self):
        self.volume.exists.return_value = False
        self.volume.create.return_value = "foo_data"

        self.assertTrue(main.restore_backup("foo_data", "/foo", "b.tar.gz"))

        self.volume.create.assert_called_once()
        self.recovery.volume_has_content.assert_not_called()  # would mount (and create) a missing volume
        self.recovery.restore_volume_backup.assert_called_once()

    def test_existing_empty_volume_is_restored(self):
        self.assertTrue(main.restore_backup("foo_data", "/foo", "b.tar.gz"))

        self.volume.create.assert_not_called()
        self.recovery.restore_volume_backup.assert_called_once()

    def test_volume_of_running_container_is_rejected_with_message(self):
        self._containers(running=["app", "db"])

        with self.assertLogs("docker_volume_backup.main", level="ERROR") as log:
            self.assertFalse(main.restore_backup("foo_data", "/foo", "b.tar.gz"))

        self.assertIn("used by running container(s): app, db", log.output[0])
        self.assertIn("Nothing was restored", log.output[0])
        self.recovery.volume_has_content.assert_not_called()
        self.recovery.restore_volume_backup.assert_not_called()

    def test_volume_of_stopped_container_is_restored_with_warning(self):
        self._containers(stopped=["app"])

        with self.assertLogs("docker_volume_backup.main", level="WARNING") as log:
            self.assertTrue(main.restore_backup("foo_data", "/foo", "b.tar.gz"))

        self.assertIn("used by stopped container(s): app", log.output[0])
        self.recovery.restore_volume_backup.assert_called_once()

    def test_content_confirmed_in_terminal(self):
        self.recovery.volume_has_content.return_value = True
        self._stdin(tty=True)

        for answer in ("y", "Y", " yes "):
            with self.subTest(answer=answer), patch("builtins.input", return_value=answer) as prompt:
                self.recovery.restore_volume_backup.reset_mock()
                self.assertTrue(main.restore_backup("foo_data", "/foo", "b.tar.gz"))

                prompt.assert_called_once()
                self.assertIn("already contains files", prompt.call_args.args[0])
                self.recovery.restore_volume_backup.assert_called_once()

    def test_content_declined_in_terminal(self):
        self.recovery.volume_has_content.return_value = True
        self._stdin(tty=True)

        for answer in ("", "n", "no", "maybe"):
            with self.subTest(answer=answer), patch("builtins.input", return_value=answer):
                self.assertFalse(main.restore_backup("foo_data", "/foo", "b.tar.gz"))

        self.recovery.restore_volume_backup.assert_not_called()

    def test_content_with_yes_option_is_restored_without_question(self):
        self.recovery.volume_has_content.return_value = True
        self._stdin(tty=True)

        with patch("builtins.input", side_effect=AssertionError("no question expected")), \
                self.assertLogs("docker_volume_backup.main", level="WARNING"):
            self.assertTrue(main.restore_backup("foo_data", "/foo", "b.tar.gz", assume_yes=True))

        self.recovery.restore_volume_backup.assert_called_once()

    def test_content_without_terminal_is_restored_as_before_with_warning(self):
        self.recovery.volume_has_content.return_value = True
        self._stdin(tty=False)

        with patch("builtins.input", side_effect=AssertionError("no question expected")), \
                self.assertLogs("docker_volume_backup.main", level="WARNING") as log:
            self.assertTrue(main.restore_backup("foo_data", "/foo", "b.tar.gz"))

        self.assertIn("already contains files", log.output[0])
        self.recovery.restore_volume_backup.assert_called_once()

    def test_never_exits_silently(self):
        """a rejected restore returns False (exit code 1) instead of ending the process with exit code 0"""
        self._containers(running=["app"])

        with self.assertLogs("docker_volume_backup.main", level="ERROR"):
            result = main.restore_backup("foo_data", "/foo", "b.tar.gz")

        self.assertIs(False, result)


class TestInitEnvironment(TestCase):

    def setUp(self):
        self.calls = MagicMock()
        patches = [
            patch.object(main, "load_dotenv", self.calls.load_dotenv),
            patch.object(main, "EnvSettings", self.calls.EnvSettings),
            patch.object(main.ArgParser, "parse_cli_args", self.calls.parse_cli_args),
            patch.object(main.Logger, "init_logger", self.calls.init_logger),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_backup_initializes_environment_in_order_and_logs_per_container(self):
        args = MagicMock(backup=True, restore=False, container="foo_bar", loglevel=20)
        self.calls.parse_cli_args.return_value = args

        self.assertIs(args, main.init_environment())

        self.assertEqual(["load_dotenv", "EnvSettings", "EnvSettings().validate", "parse_cli_args", "init_logger"],
                         [c[0] for c in self.calls.mock_calls])
        self.calls.init_logger.assert_called_once_with(20, "foo_bar")

    def test_restore_logs_per_volume(self):
        args = MagicMock(backup=False, restore=True, dockervolume="foo_data", loglevel=10)
        self.calls.parse_cli_args.return_value = args

        main.init_environment()

        self.calls.init_logger.assert_called_once_with(10, "restore-foo_data")

    def test_invalid_env_settings_stop_before_logger_init(self):
        self.calls.EnvSettings.return_value.validate.side_effect = ValueError("CHAT_ALERTING invalid")

        with self.assertRaises(ValueError):
            main.init_environment()

        self.calls.parse_cli_args.assert_not_called()
        self.calls.init_logger.assert_not_called()


class TestImport(TestCase):

    def test_import_has_no_side_effects(self):
        """importing main must neither parse the command line, nor load .env, nor create log files"""
        src_dir = os.path.join(os.path.dirname(os.path.abspath(main.__file__)), os.pardir)

        with tempfile.TemporaryDirectory() as workdir:
            with open(os.path.join(workdir, ".env"), "w") as env_file:
                env_file.write("CHAT_ALERTING=INVALID_VALUE\n")  # would fail validation if it was loaded

            result = subprocess.run([sys.executable, "-c", "import docker_volume_backup.main"], cwd=workdir,
                                    env={**os.environ, "PYTHONPATH": src_dir}, capture_output=True, text=True)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual([".env"], os.listdir(workdir))
