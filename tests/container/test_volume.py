from unittest import TestCase
from unittest.mock import MagicMock, patch

from python_on_whales import DockerException

from docker_volume_backup.container.volume import Volume


def _container(name):
    container = MagicMock()
    container.name = name
    return container


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

    @patch("docker_volume_backup.container.volume.docker.volume.exists",
           side_effect=DockerException(command_launched=["docker volume inspect foo"], return_code=1))
    def test_exists_error_is_logged_with_message(self, mock_volume):
        with self.assertLogs("docker_volume_backup.container.volume", level="ERROR") as log:
            with self.assertRaises(DockerException):
                Volume("foo").exists()

        self.assertIn("Error check volume exists: ", log.output[0])
        self.assertIn("It returned with code 1", log.output[0])

    @patch("docker_volume_backup.container.volume.docker.volume.exists", return_value=True)
    @patch("docker_volume_backup.container.volume.docker.volume.create", return_value="foo_data")
    def test_create_returns_name_of_new_volume(self, mock_create, mock_exists):
        self.assertEqual("foo_data", Volume("foo_data").create())

    @patch("docker_volume_backup.container.volume.docker.container.list")
    def test_containers_running_only(self, container_list):
        container_list.return_value = [_container("b_app"), _container("a_db")]

        self.assertEqual(["a_db", "b_app"], Volume("foo_data").containers(running_only=True))
        container_list.assert_called_once_with(all=False, filters=[("volume", "foo_data")])

    @patch("docker_volume_backup.container.volume.docker.container.list")
    def test_containers_including_stopped(self, container_list):
        container_list.return_value = [_container("app")]

        self.assertEqual(["app"], Volume("foo_data").containers())
        container_list.assert_called_once_with(all=True, filters=[("volume", "foo_data")])

    @patch("docker_volume_backup.container.volume.docker.container.list", return_value=[])
    def test_containers_none(self, container_list):
        self.assertEqual([], Volume("foo_data").containers())

    @patch("docker_volume_backup.container.volume.docker.container.list",
           side_effect=DockerException(command_launched=["docker ps"], return_code=1))
    def test_containers_error_is_logged_with_message(self, container_list):
        with self.assertLogs("docker_volume_backup.container.volume", level="ERROR") as log:
            with self.assertRaises(DockerException):
                Volume("foo_data").containers()

        self.assertIn("Error determine containers of volume: ", log.output[0])
        self.assertIn("It returned with code 1", log.output[0])
