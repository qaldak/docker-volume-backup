from unittest import TestCase
from unittest.mock import patch

from python_on_whales import DockerException

from docker_volume_backup.container.volume import Volume


class TestVolume(TestCase):
    @patch("docker_volume_backup.container.volume.docker.volume.exists", return_value=True)
    def test_exists_true(self, mock_volume):
        volume = Volume("foo")
        self.assertTrue(volume.exists(), f"Volume '{volume.name}' not found, but should")

    @patch("docker_volume_backup.container.volume.docker.volume.exists", return_value=False)
    def test_exists_false(self, mock_volume):
        volume = Volume("foo")
        self.assertFalse(volume.exists(), f"Volume '{volume.name}' found, but should not")

    @patch("docker_volume_backup.container.volume.docker.volume.exists", return_value=True)
    @patch("docker_volume_backup.container.volume.docker.volume.create", return_value="foo_data")
    def test_create_successfully(self, mock_volume, mock_exists):
        with self.assertLogs("docker_volume_backup.container.volume", level="INFO") as log:
            Volume("foo").create()
            self.assertEqual(
                ["INFO:docker_volume_backup.container.volume:Volume 'foo_data' successfully created."], log.output)

    @patch("docker_volume_backup.container.volume.docker.volume.exists", return_value=False)
    @patch("docker_volume_backup.container.volume.docker.volume.create", return_value="foo_data")
    def test_create_but_not_exists(self, mock_volume, mock_exists):
        with self.assertLogs("docker_volume_backup.container.volume", level="ERROR") as log:
            with self.assertRaises(AttributeError) as err:
                new_volume = Volume("foo").create()
            self.assertEqual("Error: volume 'foo_data' created, but not exists.", str(err.exception))
            self.assertEqual(
                '["ERROR:docker_volume_backup.container.volume:Error: volume \'foo_data\' created, but not exists."]',
                str(log.output))

    @patch("docker_volume_backup.container.volume.docker.volume.create", side_effect=DockerException(
        command_launched=["docker volume create foo_data"], return_code=1,
        stderr=b"error during connect: this error may indicate that the docker daemon is not running"))
    def test_docker_daemon_not_running(self, mock_error):
        with self.assertRaises(DockerException) as err:
            new_volume = Volume("foo").create()
        self.assertEqual(1, err.exception.return_code)
        self.assertEqual("error during connect: this error may indicate that the docker daemon is not running",
                         str(err.exception.stderr))
        log = self.assertLogs("container.volume", level="ERROR")
        print(log.logger_name)

    @patch("docker_volume_backup.container.volume.docker.volume.list",
           return_value=["python_on_whales.Volume(name='foo_data', driver=local)"])
    def test_docker_volume_in_use(self, mock_volume):
        self.assertTrue(Volume("foo").in_use(), "Volume not in use, but should.")

    @patch("docker_volume_backup.container.volume.docker.volume.list", return_value=[])
    def test_docker_volume_not_in_use(self, mock_volume):
        self.assertFalse(Volume("foo").in_use(), "Volume not in use, but should.")
