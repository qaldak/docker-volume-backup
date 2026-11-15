import os
import subprocess
import sys
import tempfile
from unittest import TestCase
from unittest.mock import MagicMock, patch

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
                         sourcepath=None)

        with patch.object(main, "restore_backup", return_value=True) as restore_backup, \
                patch.object(main, "create_backup") as create_backup:
            self.assertEqual(0, main.main(args))

        restore_backup.assert_called_once_with("foo_data", "/foo", "b.tar.gz", None)
        create_backup.assert_not_called()

    def test_exit_code_is_one_if_restored_volume_is_incomplete(self):
        args = MagicMock(backup=False, restore=True, dockervolume="foo_data", targetpath="/foo", backupfile="b.tar.gz",
                         sourcepath=None)

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

    def test_source_path_is_checked_before_docker_volume_is_touched(self):
        main.Recovery.return_value.resolve_source_path.side_effect = ValueError("contains 2 paths")

        with self.assertRaises(ValueError):
            main.restore_backup("foo_data", "/foo", "b.tar.gz")

        main.Volume.assert_not_called()
        main.Recovery.return_value.restore_volume_backup.assert_not_called()

    def test_restore_passes_source_path_and_works_without_it(self):
        main.Volume.return_value.exists.return_value = True
        main.Volume.return_value.in_use.return_value = False

        main.restore_backup("foo_data", "/foo", "b.tar.gz")
        main.Recovery.assert_called_with(docker_volume="foo_data", target_path="/foo", backup_file="b.tar.gz",
                                         source_path=None)

        main.restore_backup("foo_data", "/foo", "b.tar.gz", "/foo/data")
        main.Recovery.assert_called_with(docker_volume="foo_data", target_path="/foo", backup_file="b.tar.gz",
                                         source_path="/foo/data")
        self.assertEqual(2, main.Recovery.return_value.restore_volume_backup.call_count)

    def test_restore_result_is_result_of_check(self):
        main.Volume.return_value.exists.return_value = True
        main.Volume.return_value.in_use.return_value = False

        main.Recovery.return_value.check_recovery.return_value = True
        self.assertTrue(main.restore_backup("foo_data", "/foo", "b.tar.gz"))

        main.Recovery.return_value.check_recovery.return_value = False
        self.assertFalse(main.restore_backup("foo_data", "/foo", "b.tar.gz"))


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
