from unittest import TestCase
from unittest.mock import patch

from python_on_whales import DockerException

from container.backup import Volume, create_tar_cmd


class MockContainer(TestCase):
    def __init__(self) -> None:
        super().__init__()
        self.name = "foo_bar"
        self.docker_volumes = ["/foo/data", "/foo/config"]
        self.docker_bindings = ["/bar/log"]
        self.has_docker_volume = True
        self.has_docker_bindings = True


class MockBackupDir(TestCase):
    def __init__(self) -> None:
        super().__init__()
        self.path = "/backup"


class TestVolume(TestCase):

    def test_run_backup_no_volumes(self):
        backup_dir = MockBackupDir()
        container = MockContainer()
        container.has_docker_volume = False
        container.has_docker_bindings = False

        with self.assertRaises(AssertionError) as err:
            Volume.run_backup(container, backup_dir)
            self.assertEqual(
                "No volumes to backup",
                str(err.exception))

    @patch("src.container.backup.docker.run", side_effect=DockerException(["Fake error message"], 115))
    def test_run_backup_docker_exception(self, error):
        backup_dir = MockBackupDir()
        container = MockContainer()
        with self.assertRaises(DockerException) as err:
            Volume.run_backup(container, backup_dir)
            self.assertEqual("Fake error message", str(err.exception))

    @patch("src.container.backup.docker.run", return_value="Everything is allright")
    def test_run_backup_successful(self, tmp):
        backup_dir = MockBackupDir()
        container = MockContainer()
        with self.assertLogs("container.backup", level="INFO") as log:
            Volume.run_backup(container, backup_dir)
            self.assertEqual(["INFO:container.backup:Volume backup for container 'foo_bar' successful"], log.output)


def test_create_tar_cmd():
    container = MockContainer()
    tar_cmd = create_tar_cmd(container)
    assert ["tar", "-czf", f"/backup/foo_bar_volume_backup.tar.gz", "/foo/data", "/foo/config", "/bar/log"] == tar_cmd
