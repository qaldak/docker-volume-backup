import json
import subprocess
from unittest import TestCase
from unittest.mock import patch

from container.container import Container


class TestContainer(TestCase):

    @patch("src.container.container.docker.container.exists", return_value=True)
    @patch("src.container.container.docker.container.inspect", return_value="00001234")
    def test_container_valid(self, mock_container_state, mock_container_id):
        container = Container("Foo")
        self.assertTrue(container.exists(), "Container not exist! Expected: 'True'")

    def test_container_not_valid(self):
        container = Container("Foo")
        self.assertFalse(container.exists(), "Container not exist! Expected: 'False'")

    @patch("subprocess.check_output", return_value=open("fixtures/docker_inspect_volume_only.output").read())
    def test_determine_volumes(self, mock_check_output):
        container = Container("Foo")
        container.determine_volume()
        self.assertTrue(container.has_docker_volume, "No volumes found!")
        self.assertEqual(container.docker_volumes, ["/foo/bar/baz/dir"], "Volume destination not correct!")
        self.assertFalse(container.has_docker_bindings, "Unexpected container bindings found!")
        self.assertEqual(container.docker_bindings, [], "Unexpected container bindings found!")

    @patch("subprocess.check_output", return_value=open("fixtures/docker_inspect_multiple_volumes.output").read())
    def test_determine_multiple_volumes(self, mock_check_output):
        container = Container("Foo")
        container.determine_volume()
        self.assertTrue(container.has_docker_volume, "No volumes found!")
        self.assertEqual(container.docker_volumes, ["/foo/bar/baz/dir", "/foo/bar/baz/log"],
                         "Volume destinations not correct!")
        self.assertTrue(container.has_docker_bindings, "No bindings found!")
        self.assertEqual(container.docker_bindings, ["/opt/foo/bar", "/var/log"],
                         "Binding destinations not correct!")

    @patch("subprocess.check_output", return_value=open("fixtures/docker_inspect_invalid_output.output").read())
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
