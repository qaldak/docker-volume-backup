from unittest import TestCase
from unittest.mock import patch

from python_on_whales import DockerException

from container.volume import Volume


class TestVolume(TestCase):
    @patch("src.container.volume.docker.volume.exists", return_value=True)
    def test_exists_true(self, vol):
        volume = Volume("foo")
        self.assertTrue(volume.exists(), f"Volume '{volume.name}' not found, but should")

    @patch("src.container.volume.docker.volume.exists", return_value=False)
    def test_exists_false(self, vol):
        volume = Volume("foo")
        self.assertFalse(volume.exists(), f"Volume '{volume.name}' found, but should not")

    # @patch("src.container.volume.docker.volume.create", return_value="Foobar")
    def test_create_successfully(self):
        volume = Volume("foo")
        self.assertEqual(volume.create(), "Foobar", "Volume not created")

    @patch("src.container.volume.docker.volume.create", side_effect=DockerException(
        command_launched=["docker volume create foo_data"], return_code=1,
        stderr=b"error during connect: this error may indicate that the docker daemon is not running"))
    def test_docker_daemon_not_running(self, error):
        with self.assertRaises(DockerException) as err:
            new_volume = Volume("foo").create()
        self.assertEqual(1, err.exception.return_code)
        self.assertEqual("error during connect: this error may indicate that the docker daemon is not running",
                         str(err.exception.stderr))
