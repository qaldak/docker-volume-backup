from unittest import TestCase
from unittest.mock import patch

from python_on_whales import DockerException

from container.backup import Volume, create_tar_cmd, __determine_compression_method


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

        self.assertEqual("No volumes to backup", str(err.exception))

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
            self.assertEqual(["INFO:container.backup:Execute Volume backup for container 'foo_bar'. tar command: ["
                              "'tar', 'c', '-z', '-f', '/backup/fedora-foo_bar-volume-backup.tar.gz', '/foo/data', "
                              "'/foo/config', '/bar/log']",
                              "INFO:container.backup:Volume backup for container 'foo_bar' successful"], log.output)


@patch("src.container.backup.LocalHost.get_hostname", return_value="groot")
def test_create_tar_cmd_default(host):
    container = MockContainer()
    tar_cmd = create_tar_cmd(container)
    assert ["tar", "c", "-z", "-f", f"/backup/groot-foo_bar-volume-backup.tar.gz", "/foo/data", "/foo/config",
            "/bar/log"] == tar_cmd


@patch("src.container.backup.LocalHost.get_hostname", return_value="groot")
def test_create_tar_cmd_default_bz2(host):
    with patch("container.backup.__determine_compression_method", return_value=("-j", ".bz2")):
        container = MockContainer()
        tar_cmd = create_tar_cmd(container)
        assert ["tar", "c", "-j", "-f", f"/backup/groot-foo_bar-volume-backup.tar.bz2", "/foo/data", "/foo/config",
                "/bar/log"] == tar_cmd


@patch("src.container.backup.os.getenv", return_value="GZIP")
def test_determine_compression_method_gz(env):
    assert ("-z", ".gz") == __determine_compression_method()


@patch("src.container.backup.os.getenv", return_value="BZIP2")
def test_determine_compression_method_bz2(env):
    assert ("-j", ".bz2") == __determine_compression_method()


@patch("src.container.backup.os.getenv", return_value="")
def test_determine_compression_method_default(env):
    assert ("-z", ".gz") == __determine_compression_method()
