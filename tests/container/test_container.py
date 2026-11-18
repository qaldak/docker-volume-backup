import json
import subprocess
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
