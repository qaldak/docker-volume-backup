import json
import subprocess
from unittest import TestCase
from unittest.mock import patch

import python_on_whales.exceptions

from docker_volume_backup.container.container import Container


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
