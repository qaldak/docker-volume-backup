import json
import os
import shutil
import socket
import subprocess
import tempfile
from unittest import TestCase
from unittest.mock import MagicMock, patch

import python_on_whales.exceptions

from docker_volume_backup.container.container import Container
from docker_volume_backup.util import cfg


class TestContainer(TestCase):

    @patch("docker_volume_backup.container.container.docker.container.exists", return_value=True)
    @patch("docker_volume_backup.container.container.docker.container.inspect", return_value="00001234")
    def test_container_valid(self, mock_container_id, mock_container_state):
        container = Container("Foo")
        self.assertTrue(container.exists(), "Container not exist! Expected: 'True'")

    def test_container_not_valid(self):
        container = Container("Foo")
        self.assertFalse(container.exists(), "Container not exist! Expected: 'False'")

    @patch("subprocess.check_output", return_value=open("tests/fixtures/docker_inspect_volume_only.output").read())
    def test_determine_volumes(self, mock_check_output):
        container = Container("Foo")
        container.determine_volume()
        self.assertTrue(container.has_docker_volume, "No volumes found!")
        self.assertEqual(container.docker_volumes, ["/foo/bar/baz/dir"], "Volume destination not correct!")
        self.assertFalse(container.has_docker_bindings, "Unexpected container bindings found!")
        self.assertEqual(container.docker_bindings, [], "Unexpected container bindings found!")

    @patch("subprocess.check_output", return_value=open("tests/fixtures/docker_inspect_multiple_volumes.output").read())
    def test_determine_multiple_volumes(self, mock_check_output):
        container = Container("Foo")
        container.determine_volume()
        self.assertTrue(container.has_docker_volume, "No volumes found!")
        self.assertEqual(container.docker_volumes, ["/foo/bar/baz/dir", "/foo/bar/baz/log"],
                         "Volume destinations not correct!")
        self.assertTrue(container.has_docker_bindings, "No bindings found!")
        self.assertEqual(container.docker_bindings, ["/opt/foo/bar", "/var/log"],
                         "Binding destinations not correct!")

    @patch("subprocess.check_output", return_value=open("tests/fixtures/docker_inspect_invalid_output.output").read())
    def test_determine_invalid_output(self, mock_check_output):
        container = Container("Foo")
        with self.assertRaises(json.JSONDecodeError) as err:
            container.determine_volume()
        self.assertEqual(
            "Expecting ',' delimiter: line 1 column 159 (char 158)",
            str(err.exception))

    def test_no_container_found(self):
        container = Container("Foo")
        with self.assertRaises(subprocess.CalledProcessError) as err:
            container.determine_volume()
        self.assertEqual(
            "Command '['docker', 'inspect', '-f', '{{json .Mounts}}', 'Foo']' returned non-zero exit status 1.",
            str(err.exception))

    @patch("docker_volume_backup.container.container.docker_cli.from_env")
    def test_is_container_started_by_compose(self, mock_from_env):
        mock_client = mock_from_env.return_value
        container = Container("foo")

        # Mocking the return value
        with open("tests/fixtures/docker_inspect_with_compose.json") as file:
            mock_client.containers.client.inspect_container.return_value = json.load(file)

        self.assertEqual((True, "/docker/foo/docker-compose.yml"), container._is_container_started_by_compose())

    @patch("docker_volume_backup.container.container.docker_cli.from_env")
    def test_is_container_started_by_compose_false(self, mock_from_env):
        mock_client = mock_from_env.return_value
        container = Container("foo")

        # Mocking the return value
        with open("tests/fixtures/docker_inspect_without_compose.json") as file:
            mock_client.containers.client.inspect_container.return_value = json.load(file)

        self.assertEqual((False, None), container._is_container_started_by_compose())


class TestContainerStateCheckLogging(TestCase):
    """errors of the state checks have to be logged with their message (a stray logger argument breaks logging)"""

    def _inspect_error(self, error):
        return patch("docker_volume_backup.container.container.docker.container.inspect", side_effect=error)

    def test_is_container_running_no_such_container(self):
        error = python_on_whales.exceptions.NoSuchContainer(command_launched=["docker container inspect Foo"],
                                                            return_code=1)
        with self._inspect_error(error), \
                self.assertLogs("docker_volume_backup.container.container", level="ERROR") as log:
            with self.assertRaises(python_on_whales.exceptions.NoSuchContainer):
                Container("Foo")._is_container_running()

        self.assertIn("No such container found: Foo. Error: ", log.output[0])

    def test_is_container_running_other_error(self):
        with self._inspect_error(RuntimeError("boom")), \
                self.assertLogs("docker_volume_backup.container.container", level="ERROR") as log:
            with self.assertRaises(RuntimeError):
                Container("Foo")._is_container_running()

        self.assertIn("Error occurred while check Foo is running. Error: boom", log.output[0])

    def test_is_container_stopped_no_such_container(self):
        error = python_on_whales.exceptions.NoSuchContainer(command_launched=["docker container inspect Foo"],
                                                            return_code=1)
        with self._inspect_error(error), \
                self.assertLogs("docker_volume_backup.container.container", level="ERROR") as log:
            with self.assertRaises(python_on_whales.exceptions.NoSuchContainer):
                Container("Foo")._is_container_stopped()

        self.assertIn("No such container found: Foo. Error: ", log.output[0])

    def test_is_container_stopped_other_error(self):
        with self._inspect_error(RuntimeError("boom")), \
                self.assertLogs("docker_volume_backup.container.container", level="ERROR") as log:
            with self.assertRaises(RuntimeError):
                Container("Foo")._is_container_stopped()

        self.assertIn("Error occurred while check Foo is stopped. Error: boom", log.output[0])


def _inspect_returning(*running_states):
    """docker.container.inspect that reports the given running states one after the other"""
    states = iter(running_states)

    def inspect(name):
        result = MagicMock()
        result.state.running = next(states)
        return result

    return inspect


class TestContainerState(TestCase):
    """the state checks retry with a delay and return the result of the last check"""

    def setUp(self):
        patches = [
            patch("docker_volume_backup.container.container.time.sleep"),
            patch("docker_volume_backup.container.container.docker.container.inspect"),
        ]
        self.sleep, self.inspect = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)

        for name in ("hasError", "hasWarning"):
            self.addCleanup(setattr, cfg, name, False)
        for name in ("errorMsg", "warningMsg"):
            self.addCleanup(setattr, cfg, name, "")
        cfg.hasError = cfg.hasWarning = False

    def _states(self, *running_states):
        self.inspect.side_effect = _inspect_returning(*running_states)

    def test_running_at_first_check(self):
        self._states(True)

        self.assertTrue(Container("Foo")._is_container_running())
        self.assertEqual(1, self.inspect.call_count)
        self.sleep.assert_not_called()

    def test_running_after_retries(self):
        for states in ((False, True), (False, False, True), (False, False, False, True)):
            with self.subTest(states=states):
                self.sleep.reset_mock()
                self._states(*states)

                self.assertTrue(Container("Foo")._is_container_running())
                self.assertEqual(len(states) - 1, self.sleep.call_count)

    def test_never_running(self):
        self._states(False, False, False, False)

        self.assertFalse(Container("Foo")._is_container_running())
        self.assertEqual(4, self.inspect.call_count)
        self.assertEqual(3, self.sleep.call_count)  # no waiting after the last check
        self.sleep.assert_called_with(3)

    def test_stopped_at_first_check(self):
        self._states(False)

        self.assertTrue(Container("Foo")._is_container_stopped())
        self.sleep.assert_not_called()

    def test_stopped_after_retries(self):
        self._states(True, True, False)

        self.assertTrue(Container("Foo")._is_container_stopped())
        self.assertEqual(2, self.sleep.call_count)

    def test_never_stopped(self):
        self._states(True, True, True, True)

        self.assertFalse(Container("Foo")._is_container_stopped())
        self.assertEqual(4, self.inspect.call_count)

    def test_stopped_check_does_not_use_the_running_check(self):
        """the retry of the stopped check used to call _is_container_running"""
        self._states(True, False)

        with patch.object(Container, "_is_container_running", side_effect=AssertionError("wrong check")):
            self.assertTrue(Container("Foo")._is_container_stopped())

    def test_start_succeeds_if_container_runs_after_a_retry(self):
        """used to fail with 'not (re)started properly' although the container was running at the 2nd check"""
        self._states(False, True)

        with patch.object(Container, "_is_container_started_by_compose", return_value=(False, None)), \
                patch("docker_volume_backup.container.container.docker.container.start") as start:
            Container("Foo").start()

        start.assert_called_once_with("Foo")
        self.assertFalse(cfg.hasError)

    def test_start_fails_if_container_never_runs(self):
        self._states(False, False, False, False)

        with patch.object(Container, "_is_container_started_by_compose", return_value=(False, None)), \
                patch("docker_volume_backup.container.container.docker.container.start"):
            with self.assertRaises(RuntimeError) as err:
                Container("Foo").start()

        self.assertIn("not (re)started properly", str(err.exception))
        self.assertTrue(cfg.hasError)

    def test_stop_without_warning_if_container_stops_after_a_retry(self):
        """used to report 'not stopped properly' although the container was stopped at the 2nd check"""
        self._states(True, False)

        with patch.object(Container, "_is_container_started_by_compose", return_value=(False, None)), \
                patch("docker_volume_backup.container.container.docker.container.stop"):
            Container("Foo").stop()

        self.assertFalse(cfg.hasWarning)

    def test_stop_warns_if_container_never_stops(self):
        self._states(True, True, True, True)

        with patch.object(Container, "_is_container_started_by_compose", return_value=(False, None)), \
                patch("docker_volume_backup.container.container.docker.container.stop"), \
                self.assertLogs("docker_volume_backup.container.container", level="WARNING"):
            Container("Foo").stop()

        self.assertTrue(cfg.hasWarning)
        self.assertIn("not stopped properly", cfg.warningMsg)


class TestContainerBindMounts(TestCase):
    """which paths are backed up for bind mounts: directories, files, sockets, nested paths"""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def _source(self, kind, name="source"):
        """create a real source on the host: dir, file, socket or fifo"""
        path = os.path.join(self.dir, name)
        if kind == "dir":
            os.mkdir(path)
        elif kind == "file":
            open(path, "w").close()
        elif kind == "fifo":
            os.mkfifo(path)
        elif kind == "socket":
            sock = socket.socket(socket.AF_UNIX)
            sock.bind(path)
            self.addCleanup(sock.close)
        return path

    @staticmethod
    def _mount(destination, source="/does/not/exist", mount_type="bind", rw=True):
        return {"Type": mount_type, "Source": source, "Destination": destination, "RW": rw, "Mode": "", "Name": ""}

    def _determine(self, *mounts):
        container = Container("Foo")
        with patch("subprocess.check_output", return_value=json.dumps(list(mounts))):
            container.determine_volume()
        return container

    def test_directory_with_extension_like_name_is_backed_up_itself(self):
        """/etc/mosquitto/conf.d and /data/v1.2 used to be taken for files: their parent directory was backed up"""
        source = self._source("dir")
        for destination in ("/etc/mosquitto/conf.d", "/data/v1.2", "/data/backup.d"):
            with self.subTest(destination=destination):
                container = self._determine(self._mount(destination, source))

                self.assertEqual([destination], container.docker_bindings)
                self.assertTrue(container.has_docker_bindings)

    def test_directory_without_extension_is_backed_up_itself(self):
        container = self._determine(self._mount("/var/log/app/", self._source("dir")))

        self.assertEqual(["/var/log/app"], container.docker_bindings)

    def test_file_with_extension_keeps_backing_up_its_directory(self):
        """as before: the directory of a file with an extension (e.g. the config directory of a config file)"""
        container = self._determine(self._mount("/opt/foo/bar/file.conf", self._source("file")))

        self.assertEqual(["/opt/foo/bar"], container.docker_bindings)

    def test_file_without_extension_is_backed_up_itself(self):
        container = self._determine(self._mount("/etc/hosts_custom", self._source("file")))

        self.assertEqual(["/etc/hosts_custom"], container.docker_bindings)

    def test_file_directly_below_root_is_backed_up_itself(self):
        """/config.json used to give '/' (and an empty tar argument): the file itself is backed up"""
        container = self._determine(self._mount("/config.json", self._source("file")))

        self.assertEqual(["/config.json"], container.docker_bindings)

    def test_unknown_source_is_decided_by_the_name_as_before(self):
        """source not accessible (e.g. no permission): same rule as before"""
        container = self._determine(self._mount("/opt/foo/bar/file.conf"), self._mount("/var/log"))

        self.assertEqual(["/opt/foo/bar", "/var/log"], container.docker_bindings)

    def test_socket_fifo_and_device_are_not_backed_up(self):
        for kind in ("socket", "fifo"):
            with self.subTest(kind=kind):
                path = self._source(kind, name=f"{kind}.sock")

                with self.assertLogs("docker_volume_backup.container.container", level="WARNING") as log:
                    container = self._determine(self._mount("/var/run/docker.sock", path))

                self.assertEqual([], container.docker_bindings)
                self.assertFalse(container.has_docker_bindings)
                self.assertIn("is a socket, FIFO or device and is not backed up", log.output[0])

        with self.assertLogs("docker_volume_backup.container.container", level="WARNING"):
            container = self._determine(self._mount("/dev/null", "/dev/null"))
        self.assertEqual([], container.docker_bindings)

    def test_container_with_only_a_socket_has_nothing_to_back_up(self):
        socket_path = self._source("socket", name="docker.sock")

        with patch("subprocess.check_output",
                   return_value=json.dumps([self._mount("/var/run/docker.sock", socket_path)])), \
                self.assertLogs("docker_volume_backup.container.container", level="WARNING"):
            self.assertFalse(Container("Foo").is_volume_available())

    def test_other_mounts_are_still_backed_up_next_to_a_socket(self):
        socket_path = self._source("socket", name="docker.sock")

        with self.assertLogs("docker_volume_backup.container.container", level="WARNING"):
            container = self._determine(self._mount("/var/run/docker.sock", socket_path),
                                        self._mount("/data", mount_type="volume"))

        self.assertEqual(["/data"], container.docker_volumes)
        self.assertEqual([], container.docker_bindings)

    def test_read_only_and_other_mount_types_are_not_backed_up(self):
        container = self._determine(self._mount("/usr/foo", rw=False), self._mount("/run/tmp", mount_type="tmpfs"),
                                    self._mount("/data", mount_type="volume", rw=False))

        self.assertEqual(([], []), (container.docker_volumes, container.docker_bindings))

    def test_nested_paths_are_backed_up_once(self):
        container = self._determine(self._mount("/data", mount_type="volume"),
                                    self._mount("/data/sub", self._source("dir")),
                                    self._mount("/data/sub/notes.txt", self._source("file", name="notes")),
                                    self._mount("/data2", self._source("dir", name="data2")))

        self.assertEqual(["/data"], container.docker_volumes)
        self.assertEqual(["/data2"], container.docker_bindings)  # /data2 is not inside /data

    def test_nested_volume_is_removed_if_a_binding_contains_it(self):
        container = self._determine(self._mount("/srv", self._source("dir")),
                                    self._mount("/srv/db", mount_type="volume"))

        self.assertEqual(([], ["/srv"]), (container.docker_volumes, container.docker_bindings))
        self.assertFalse(container.has_docker_volume)

    def test_duplicates_with_trailing_slash_are_removed(self):
        container = self._determine(self._mount("/data/", mount_type="volume"),
                                    self._mount("/data", mount_type="volume"))

        self.assertEqual(["/data"], container.docker_volumes)

    def test_mount_at_root_is_not_backed_up(self):
        with self.assertLogs("docker_volume_backup.container.container", level="WARNING") as log:
            container = self._determine(self._mount("/", mount_type="volume"))

        self.assertEqual([], container.docker_volumes)
        self.assertIn("is not backed up", log.output[0])

    def test_determine_volume_twice_gives_the_same_result(self):
        container = Container("Foo")
        output = json.dumps([self._mount("/data", mount_type="volume"), self._mount("/opt/a/b.conf")])

        with patch("subprocess.check_output", return_value=output):
            container.determine_volume()
            container.determine_volume()

        self.assertEqual((["/data"], ["/opt/a"]), (container.docker_volumes, container.docker_bindings))

    def test_no_empty_or_root_path_reaches_the_tar_command(self):
        """the paths of all kinds of mounts end up in the tar command: none of them may be empty or '/'"""
        from docker_volume_backup.container.backup import Backup

        container = self._determine(self._mount("/config.json", self._source("file")),
                                    self._mount("/data/", mount_type="volume"),
                                    self._mount("/etc/mosquitto/conf.d", self._source("dir", name="d")))
        backup_dir = MagicMock()
        backup_dir.path = "/foo/backup"

        with patch("docker_volume_backup.container.backup.LocalHost.get_hostname", return_value="h"):
            tar_cmd = Backup(container=container, backup_dir=backup_dir)._create_tar_cmd()

        paths = tar_cmd[tar_cmd.index("-C") + 2:]
        self.assertEqual(["data", "config.json", "etc/mosquitto/conf.d"], paths)
        self.assertTrue(all(path and path != "/" for path in paths))
