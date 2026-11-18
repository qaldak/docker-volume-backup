import calendar
import os
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime
from unittest import TestCase, skipIf
from unittest.mock import patch

from python_on_whales import DockerException

from docker_volume_backup.container.backup import Backup
from docker_volume_backup.util import cfg


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


def calendar_days(year, month):
    return calendar.monthrange(year, month)[1]


def _unwrap(cmd):
    """command of the helper container without the umask wrapper: sh -c 'umask ...; exec "$@"' sh <cmd>"""
    if cmd[0] == "sh" and "tar -t" not in cmd[2]:  # the verification command runs without the umask wrapper
        assert cmd[1] == "-c" and cmd[2].startswith("umask ") and cmd[3] == "sh", cmd
        return cmd[4:]
    return cmd


def _kind(cmd):
    """name of a command of the helper container: tar, verify (tar -t), mv, rm, ..."""
    if cmd[0] == "sh" and cmd[1] == "-c" and "tar -t" in cmd[2]:
        return "verify"
    return _unwrap(cmd)[0]


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

    @patch.dict("docker_volume_backup.container.backup.os.environ", {}, clear=True)
    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.os.path.getsize", return_value=1234)
    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    @patch("docker_volume_backup.container.backup.docker.run", return_value="")
    def test_run_backup_replaces_backup_file_only_after_tar(self, docker_run, hostname, filesize, should_refresh):
        Backup(container=MockContainer(), backup_dir=MockBackupDir()).run_backup()

        # tar runs with the umask of the backup file permissions, so the file is never created wider
        self.assertEqual(["sh", "-c", 'umask 0137; exec "$@"', "sh", "tar"], docker_run.call_args_list[0].args[1][:5])

        commands = [_unwrap(call.args[1]) for call in docker_run.call_args_list]
        self.assertEqual(["tar", "sh", "mv"], [command[0] for command in commands], commands)
        self.assertEqual("/backup/groot-foo_bar-volume-backup.tar.gz.tmp", commands[0][commands[0].index("-f") + 1])
        self.assertEqual(["mv", "-f", "/backup/groot-foo_bar-volume-backup.tar.gz.tmp",
                          "/backup/groot-foo_bar-volume-backup.tar.gz"], commands[2])

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    @patch("docker_volume_backup.container.backup.docker.run")
    def test_run_backup_failing_tar_keeps_last_backup_and_removes_tmp_file(self, docker_run, hostname, should_refresh):
        docker_run.side_effect = [DockerException(command_launched=["tar"], return_code=1), ""]

        with self.assertRaises(DockerException) as err:
            Backup(container=MockContainer(), backup_dir=MockBackupDir()).run_backup()

        self.assertEqual(1, err.exception.return_code)
        commands = [_unwrap(call.args[1]) for call in docker_run.call_args_list]
        self.assertEqual(2, len(commands), commands)
        self.assertEqual("tar", commands[0][0])
        self.assertEqual(["rm", "-f", "/backup/groot-foo_bar-volume-backup.tar.gz.tmp"], commands[1])
        self.assertNotIn("mv", [command[0] for command in commands])

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    @patch("docker_volume_backup.container.backup.docker.run")
    def test_run_backup_failing_replace_removes_tmp_file(self, docker_run, hostname, should_refresh):
        docker_run.side_effect = ["", "", DockerException(command_launched=["mv"], return_code=1), ""]

        with self.assertRaises(DockerException):
            Backup(container=MockContainer(), backup_dir=MockBackupDir()).run_backup()

        commands = [_kind(call.args[1]) for call in docker_run.call_args_list]
        self.assertEqual(["tar", "verify", "mv", "rm"], commands)

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
    @patch("docker_volume_backup.container.backup.os.getuid", return_value=0)
    def test_should_change_filesettings_false_true(self, getuid):
        container = MockContainer()
        backup_dir = MockBackupDir()
        backup = Backup(container=container, backup_dir=backup_dir)
        self.assertEqual((False, True), backup.should_change_filesettings())

    @patch("docker_volume_backup.container.backup.os.getuid", return_value=0)
    def test_should_change_filesettings_false_false(self, getuid):
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
    @patch("docker_volume_backup.container.backup.docker.image.pull")
    @patch("docker_volume_backup.container.backup.docker.run", return_value="Everything is allright")
    def test_exec_docker_run_pulls_once_on_refresh_day(self, docker_run, image_pull, should_refresh):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        for _ in range(3):  # tar, chown, chmod, ... of one run
            backup._exec_docker_run(["chown", "1000", backup.backup_file])

        image_pull.assert_called_once_with("busybox:latest", quiet=True)  # quiet: no progress output in cron mail
        self.assertEqual(3, docker_run.call_count)
        for call in docker_run.call_args_list:
            self.assertEqual("missing", call.kwargs["pull"])

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=True)
    @patch("docker_volume_backup.container.backup.docker.image.pull",
           side_effect=DockerException(command_launched=["docker image pull busybox:latest"], return_code=1,
                                       stderr=b"dial tcp: lookup registry-1.docker.io: no such host"))
    @patch("docker_volume_backup.container.backup.docker.run", return_value="Everything is allright")
    def test_exec_docker_run_continues_with_cached_image_if_pull_fails(self, docker_run, image_pull, should_refresh):
        cfg.hasWarning = False
        cfg.warningMsg = ""
        self.addCleanup(setattr, cfg, "hasWarning", False)
        self.addCleanup(setattr, cfg, "warningMsg", "")
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        with self.assertLogs("docker_volume_backup.container.backup", level="WARNING") as log:
            self.assertEqual("Everything is allright", backup._exec_docker_run(["chown", "1000", backup.backup_file]))
            backup._exec_docker_run(["chmod", "640", backup.backup_file])

        self.assertEqual(1, len(log.output), log.output)
        self.assertIn("could not be refreshed from the registry. Continue with the cached image", log.output[0])
        self.assertIn("no such host", log.output[0])
        self.assertTrue(cfg.hasWarning)
        self.assertIn("Continue with the cached image", cfg.warningMsg)
        image_pull.assert_called_once()  # no retry for every helper run
        self.assertEqual(2, docker_run.call_count)

    @patch.dict("docker_volume_backup.container.backup.os.environ", {}, clear=True)
    @patch("docker_volume_backup.container.backup.os.path.getsize", return_value=1234)
    @patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot")
    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=True)
    @patch("docker_volume_backup.container.backup.docker.image.pull",
           side_effect=DockerException(command_launched=["docker image pull busybox:latest"], return_code=1))
    @patch("docker_volume_backup.container.backup.docker.run", return_value="")
    def test_run_backup_succeeds_if_registry_is_not_reachable_on_refresh_day(self, docker_run, image_pull,
                                                                             should_refresh, hostname, filesize):
        self.addCleanup(setattr, cfg, "hasWarning", False)
        self.addCleanup(setattr, cfg, "warningMsg", "")

        with self.assertLogs("docker_volume_backup.container.backup", level="WARNING"):
            Backup(container=MockContainer(), backup_dir=MockBackupDir()).run_backup()

        self.assertEqual(["tar", "verify", "mv"], [_kind(call.args[1]) for call in docker_run.call_args_list])
        image_pull.assert_called_once()

    @patch.dict("docker_volume_backup.container.backup.os.environ", {"BASE_IMAGE": "alpine:3.20"}, clear=True)
    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=True)
    @patch("docker_volume_backup.container.backup.docker.image.pull")
    @patch("docker_volume_backup.container.backup.docker.run", return_value="")
    def test_image_from_env_is_pulled_and_used(self, docker_run, image_pull, should_refresh):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        backup._exec_docker_run(["chown", "1000", backup.backup_file])

        image_pull.assert_called_once_with("alpine:3.20", quiet=True)
        self.assertEqual("alpine:3.20", docker_run.call_args.args[0])

    @patch.dict("docker_volume_backup.container.backup.os.environ", {}, clear=True)
    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.docker.run", return_value="")
    def test_default_image_without_env_setting(self, docker_run, should_refresh):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        backup._exec_docker_run(["chown", "1000", backup.backup_file])

        self.assertEqual("busybox:latest", docker_run.call_args.args[0])

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.docker.image.pull")
    @patch("docker_volume_backup.container.backup.docker.run", return_value="Everything is allright")
    def test_exec_docker_run_does_not_pull_on_other_days(self, docker_run, image_pull, should_refresh):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        backup._exec_docker_run(["chown", "1000", backup.backup_file])

        image_pull.assert_not_called()

    def _should_refresh_on(self, refresh_day, today):
        with patch.dict("docker_volume_backup.container.backup.os.environ", {"IMAGE_REFRESH_DAY": refresh_day}), \
                patch("docker_volume_backup.container.backup.datetime") as mock_datetime:
            mock_datetime.now.return_value = today
            return Backup._should_refresh_image()

    def test_refresh_day_beyond_end_of_month_uses_last_day_of_month(self):
        cases = [("31", datetime(2026, 1, 31), True), ("31", datetime(2026, 4, 30), True),
                 ("31", datetime(2026, 4, 29), False), ("31", datetime(2026, 2, 28), True),
                 ("31", datetime(2026, 2, 27), False), ("30", datetime(2026, 2, 28), True),
                 ("29", datetime(2026, 2, 28), True), ("29", datetime(2028, 2, 29), True),
                 ("29", datetime(2028, 2, 28), False)]

        for refresh_day, today, expected in cases:
            with self.subTest(refresh_day=refresh_day, today=today.date()):
                self.assertEqual(expected, self._should_refresh_on(refresh_day, today))

    def test_refresh_day_within_month_is_unchanged(self):
        self.assertTrue(self._should_refresh_on("15", datetime(2026, 4, 15)))
        self.assertFalse(self._should_refresh_on("15", datetime(2026, 4, 30)))
        self.assertFalse(self._should_refresh_on("1", datetime(2026, 4, 30)))

    def test_exactly_one_refresh_day_per_month(self):
        """every month has a day on which the image is refreshed, also with the highest configured day"""
        for refresh_day in ("1", "15", "29", "30", "31"):
            for month in range(1, 13):
                days = [datetime(2027, month, day) for day in range(1, calendar_days(2027, month) + 1)]
                with self.subTest(refresh_day=refresh_day, month=month):
                    self.assertEqual(1, sum(self._should_refresh_on(refresh_day, today) for today in days))

    @patch("docker_volume_backup.container.backup.os.path.getsize", side_effect=FileNotFoundError("no such file"))
    def test_get_backup_file_size_missing_file_is_logged(self, filesize):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        with self.assertLogs("docker_volume_backup.container.backup", level="ERROR") as log:
            with self.assertRaises(FileNotFoundError):
                backup._get_backup_file_size()

        self.assertIn("Not able to determine file size. Backup file not found: /foo/backup/", log.output[0])

    @patch("docker_volume_backup.container.backup.os.getgid", return_value=1001)
    @patch("docker_volume_backup.container.backup.os.getuid", return_value=1000)
    @patch.dict("docker_volume_backup.container.backup.os.environ", {}, clear=True)
    def test_file_owner_defaults_to_user_running_the_backup(self, getuid, getgid):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        self.assertEqual(("1000", "1001"), (backup.new_user_id, backup.new_group_id))
        self.assertEqual((True, False), backup.should_change_filesettings())

    @patch("docker_volume_backup.container.backup.os.getuid", return_value=0)
    @patch.dict("docker_volume_backup.container.backup.os.environ", {}, clear=True)
    def test_file_owner_not_changed_if_backup_runs_as_root(self, getuid):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        self.assertEqual((None, None), (backup.new_user_id, backup.new_group_id))
        self.assertEqual((False, False), backup.should_change_filesettings())

    @patch("docker_volume_backup.container.backup.os.getgid", return_value=1001)
    @patch("docker_volume_backup.container.backup.os.getuid", return_value=1000)
    @patch.dict("docker_volume_backup.container.backup.os.environ",
                {"BACKUP_FILE_OWNER": "0", "BACKUP_FILE_GROUP": "0"}, clear=True)
    def test_file_owner_from_env_wins_over_default(self, getuid, getgid):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        self.assertEqual(("0", "0"), (backup.new_user_id, backup.new_group_id))

    @patch("docker_volume_backup.container.backup.os.getgid", return_value=1001)
    @patch("docker_volume_backup.container.backup.os.getuid", return_value=1000)
    @patch.dict("docker_volume_backup.container.backup.os.environ", {"BACKUP_FILE_OWNER": "4711"}, clear=True)
    def test_file_group_not_defaulted_if_owner_is_configured(self, getuid, getgid):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        self.assertEqual(("4711", None), (backup.new_user_id, backup.new_group_id))

    def _chown_command(self, env, uid=1000, gid=1001):
        with patch.dict("docker_volume_backup.container.backup.os.environ", env, clear=True), \
                patch("docker_volume_backup.container.backup.os.getuid", return_value=uid), \
                patch("docker_volume_backup.container.backup.os.getgid", return_value=gid), \
                patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot"), \
                patch("docker_volume_backup.container.backup.Backup._exec_docker_run") as run:
            Backup(container=MockContainer(), backup_dir=MockBackupDir()).change_file_ownership()
        return run.call_args.args[0]

    def test_chown_command_default_owner_and_group(self):
        self.assertEqual(["chown", "1000:1001", "/backup/groot-foo_bar-volume-backup.tar.gz"],
                         self._chown_command({}))

    def test_chown_command_group_only_changes_the_group(self):
        self.assertEqual(["chown", ":9876", "/backup/groot-foo_bar-volume-backup.tar.gz"],
                         self._chown_command({"BACKUP_FILE_GROUP": "9876"}))

    def test_chown_command_owner_only(self):
        self.assertEqual(["chown", "4711", "/backup/groot-foo_bar-volume-backup.tar.gz"],
                         self._chown_command({"BACKUP_FILE_OWNER": "4711"}))

    @patch.dict("docker_volume_backup.container.backup.os.environ", {}, clear=True)
    def test_umask_default_creates_0640(self):
        backup = Backup(container=MockContainer(), backup_dir=MockBackupDir())

        self.assertEqual("0137", backup._determine_file_umask())
        self.assertEqual(["sh", "-c", 'umask 0137; exec "$@"', "sh", "tar", "c"], backup._with_umask(["tar", "c"]))

    @patch.dict("docker_volume_backup.container.backup.os.environ", {"BACKUP_FILE_PERMS": "664"}, clear=True)
    def test_umask_follows_configured_permissions(self):
        self.assertEqual("0113", Backup(container=MockContainer(), backup_dir=MockBackupDir())._determine_file_umask())

    @patch.dict("docker_volume_backup.container.backup.os.environ", {"BACKUP_FILE_PERMS": "rwx"}, clear=True)
    def test_umask_invalid_permissions_fall_back_to_default(self):
        with self.assertLogs("docker_volume_backup.util.accessor", level="WARNING"):
            self.assertEqual("0137",
                             Backup(container=MockContainer(), backup_dir=MockBackupDir())._determine_file_umask())

    @patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False)
    @patch("docker_volume_backup.container.backup.docker.run", return_value="")
    def test_volumes_of_container_are_mounted_read_only(self, docker_run, should_refresh):
        Backup(container=MockContainer(), backup_dir=MockBackupDir())._exec_docker_run(["tar", "c"])

        self.assertEqual(["foo_bar:ro"], docker_run.call_args.kwargs["volumes_from"])

    # --- verification of the new archive before it replaces the last backup (#165) ---

    def _run_backup_with_failing(self, failing: str, env=None):
        """run_backup with a helper container whose command "failing" (tar, verify, mv) fails: returns the commands"""
        calls = []

        def docker_run(image, cmd, **kwargs):
            calls.append(_kind(cmd))
            if calls[-1] == failing:
                raise DockerException(command_launched=cmd, return_code=1)
            return ""

        with patch.dict("docker_volume_backup.container.backup.os.environ", env or {}, clear=True), \
                patch("docker_volume_backup.container.backup.Backup._should_refresh_image", return_value=False), \
                patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="groot"), \
                patch("docker_volume_backup.container.backup.os.path.getsize", return_value=1234), \
                patch("docker_volume_backup.container.backup.docker.run", side_effect=docker_run) as run:
            try:
                Backup(container=MockContainer(), backup_dir=MockBackupDir()).run_backup()
                error = None
            except Exception as err:
                error = err
        return calls, error, run

    def test_verification_runs_between_tar_and_publish(self):
        calls, error, run = self._run_backup_with_failing("none")

        self.assertIsNone(error)
        self.assertEqual(["tar", "verify", "mv"], calls)

    def test_verification_command_checks_size_and_reads_the_archive_with_the_compression_of_the_backup(self):
        _, _, run = self._run_backup_with_failing("none", {"COMPRESSION_METHOD": "BZIP2"})

        verify = run.call_args_list[1].args[1]
        self.assertEqual(['sh', '-c', 'test -s "$1" && tar -t $2 -f "$1" > /dev/null', 'sh',
                          '/backup/groot-foo_bar-volume-backup.tar.bz2.tmp', '-j'], verify)

    def test_failed_verification_keeps_last_backup_and_removes_tmp_file(self):
        calls, error, run = self._run_backup_with_failing("verify")

        self.assertEqual(["tar", "verify", "rm"], calls)  # no mv: the last backup is not replaced
        self.assertIsInstance(error, RuntimeError)
        self.assertIn("verification failed", str(error))
        self.assertIn("The last backup was not replaced", str(error))
        self.assertIsInstance(error.__cause__, DockerException)

    def test_verification_can_be_switched_off(self):
        for value in ("false", "FALSE", " false "):
            with self.subTest(value=value):
                calls, error, _ = self._run_backup_with_failing("none", {"VERIFY_BACKUP": value})

                self.assertIsNone(error)
                self.assertEqual(["tar", "mv"], calls)

    def test_verification_is_on_by_default_and_with_explicit_true(self):
        for env in ({}, {"VERIFY_BACKUP": ""}, {"VERIFY_BACKUP": "true"}, {"VERIFY_BACKUP": "TRUE"}):
            with self.subTest(env=env):
                calls, _, _ = self._run_backup_with_failing("none", env)

                self.assertEqual(["tar", "verify", "mv"], calls)

    def test_invalid_verify_setting_keeps_verification_on_and_warns(self):
        for value in ("maybe", "no", "0", "1", "yes"):
            with self.subTest(value=value):
                with self.assertLogs("docker_volume_backup.container.backup", level="WARNING") as log:
                    calls, _, _ = self._run_backup_with_failing("none", {"VERIFY_BACKUP": value})

                self.assertEqual(["tar", "verify", "mv"], calls)
                self.assertTrue(any(f"VERIFY_BACKUP not defined properly: '{value}'" in line for line in log.output),
                                log.output)

    @skipIf(shutil.which("tar") is None or shutil.which("sh") is None, "tar/sh not available")
    def test_verification_command_detects_broken_archives(self):
        """run the verification command of the helper container on the host with real archives"""
        with tempfile.TemporaryDirectory() as directory:
            src = os.path.join(directory, "src")
            os.makedirs(src)
            with open(os.path.join(src, "f"), "wb") as f:
                f.write(os.urandom(200000))

            def verify(path, flag):
                cmd = ["sh", "-c", 'test -s "$1" && tar -t $2 -f "$1" > /dev/null', "sh", path, flag]
                return subprocess.run(cmd, capture_output=True).returncode

            for flag in ("-z", "-j"):
                with self.subTest(flag=flag):
                    good = os.path.join(directory, f"good{flag}.tar")
                    subprocess.run(["tar", "c", flag, "-f", good, "-C", src, "f"], check=True)
                    with open(good, "rb") as f:
                        data = f.read()

                    broken = {"truncated": data[:len(data) - 100], "half": data[:len(data) // 2], "empty": b"",
                              "no archive": os.urandom(5000)}
                    self.assertEqual(0, verify(good, flag))
                    for name, content in broken.items():
                        path = os.path.join(directory, f"{name}{flag}.tar")
                        with open(path, "wb") as f:
                            f.write(content)
                        self.assertNotEqual(0, verify(path, flag), f"{name} {flag}")

            self.assertNotEqual(0, verify(os.path.join(directory, "missing"), "-z"))

    @skipIf(shutil.which("tar") is None or shutil.which("sh") is None, "tar/sh not available")
    @patch.dict("docker_volume_backup.container.backup.os.environ", {}, clear=True)
    def test_tar_creates_backup_file_with_0640_without_a_wider_phase(self):
        """run the wrapped tar command on the host: the file is created with the final permissions"""
        with tempfile.TemporaryDirectory() as directory:
            os.makedirs(os.path.join(directory, "src"))
            with open(os.path.join(directory, "src", "f"), "w") as f:
                f.write("x")

            cmd = Backup(container=MockContainer(), backup_dir=MockBackupDir())._with_umask(
                ["tar", "c", "-z", "-f", os.path.join(directory, "b.tar.gz"), "-C", os.path.join(directory, "src"), "f"])
            previous_umask = os.umask(0o022)
            try:
                subprocess.run(cmd, check=True)
            finally:
                os.umask(previous_umask)

            self.assertEqual(0o640, stat.S_IMODE(os.stat(os.path.join(directory, "b.tar.gz")).st_mode))
