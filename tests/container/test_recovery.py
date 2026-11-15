import os
import shutil
import subprocess
import tarfile
import tempfile
from unittest import TestCase, skipIf
from unittest.mock import patch

from docker_volume_backup.container.recovery import Recovery


class TestRecovery(TestCase):
    def test_recovery_determine_strip_length(self):
        recovery = Recovery(backup_file="/backup/path/foo.xyz", docker_volume="foo_data", target_path="/foo/bar/baz")
        self.assertEqual(recovery._determine_strip_length(), 3, "Strip length not correct")

    def test_recovery_determine_cmp_method_gz(self):
        recovery = Recovery(backup_file="/backup/path/foo.xyz.gz", docker_volume="foo_data", target_path="/foo/bar/baz")
        self.assertEqual(recovery._determine_cmp_method(), "-z", "Determine compression method failed")

    def test_recovery_determine_cmp_method_bz2(self):
        recovery = Recovery(backup_file="/backup/path/foo.xyz.bz2", docker_volume="foo_data",
                            target_path="/foo/bar/baz")
        self.assertEqual(recovery._determine_cmp_method(), "-j", "Determine compression method failed")

    def test_recovery_create_backup_cmd(self):
        recovery = Recovery(backup_file="/backup/path/foo.xyz.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")
        self.assertEqual(recovery._create_tar_cmd(),
                         ["tar", "-x", "-z", "-v", "-f", "/backup/foo.xyz.gz", "--strip-components=3", "-C",
                          "/foo/bar/baz"], "Backup command failed")


def _create_backup_file(directory, files, compression="gz", roots=None, dot_prefix=False):
    """
    Create a backup file like the backup does: one tar file with a path per mount, names without leading '/'.

    :param files: dict with file path in the container -> content
    :param roots: paths of the mounts (default: all given files)
    :param dot_prefix: store names with leading './' (as older backup files)
    """
    source_dir = os.path.join(directory, "src")
    for file, content in files.items():
        path = os.path.join(source_dir, file.lstrip("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    backup_file = os.path.join(directory, f"backup.tar.{compression}")
    with tarfile.open(backup_file, f"w:{compression}") as tar:
        for root in roots if roots is not None else list(files):
            arcname = ("./" if dot_prefix else "") + root.lstrip("/")
            tar.add(os.path.join(source_dir, root.lstrip("/")), arcname=arcname)

    return backup_file


MULTI_MOUNT_FILES = {"/foo/data/a": "a", "/foo/data/sub/s": "s", "/foo/config/b": "b", "/bar/log/c": "c",
                     "/foo/x.conf": "x"}
MULTI_MOUNT_ROOTS = ["/foo/data", "/foo/config", "/bar/log", "/foo/x.conf"]


class TestRecoverySourcePath(TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def _recovery(self, backup_file, target_path="/foo/data", source_path=None):
        return Recovery(backup_file=backup_file, docker_volume="foo_data", target_path=target_path,
                        source_path=source_path)

    def test_determine_archive_roots(self):
        roots = Recovery._determine_archive_roots(
            ["foo/data", "foo/data/a", "foo/data/sub/s", "foo/config", "bar/log/c", "bar/log"])
        self.assertEqual(["bar/log", "foo/config", "foo/data"], roots)

    def test_determine_archive_roots_nested_mount_is_part_of_parent(self):
        self.assertEqual(["data"], Recovery._determine_archive_roots(["data", "data/sub", "data/sub/f"]))

    def test_single_mount_backup_keeps_legacy_command(self):
        backup_file = _create_backup_file(self.dir, {"/foo/data/a": "a"}, roots=["/foo/data"])
        recovery = self._recovery(backup_file, "/foo/data")

        recovery.resolve_source_path()

        self.assertEqual(["tar", "-x", "-z", "-v", "-f", "/backup/backup.tar.gz", "--strip-components=2", "-C",
                          "/foo/data"], recovery._create_tar_cmd())

    def test_legacy_fixture_without_source_path_keeps_legacy_command(self):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        recovery.resolve_source_path()

        self.assertEqual(["tar", "-x", "-z", "-v", "-f", "/backup/tst-backup.tar.gz", "--strip-components=3", "-C",
                          "/foo/bar/baz"], recovery._create_tar_cmd())

    def test_multi_mount_backup_without_source_path_is_rejected(self):
        backup_file = _create_backup_file(self.dir, MULTI_MOUNT_FILES, roots=MULTI_MOUNT_ROOTS)

        with self.assertRaises(ValueError) as err:
            self._recovery(backup_file).resolve_source_path()

        message = str(err.exception)
        self.assertIn("contains 4 paths", message)
        self.assertIn("/bar/log, /foo/config, /foo/data, /foo/x.conf", message)
        self.assertIn("--sourcepath", message)

    def test_source_path_not_in_backup_file(self):
        backup_file = _create_backup_file(self.dir, MULTI_MOUNT_FILES, roots=MULTI_MOUNT_ROOTS)

        with self.assertRaises(ValueError) as err:
            self._recovery(backup_file, source_path="/foo/missing").resolve_source_path()

        self.assertIn("'/foo/missing' not found", str(err.exception))
        self.assertIn("/foo/data", str(err.exception))

    def test_source_path_parent_of_mounts_is_rejected(self):
        backup_file = _create_backup_file(self.dir, MULTI_MOUNT_FILES, roots=MULTI_MOUNT_ROOTS)

        with self.assertRaises(ValueError):
            self._recovery(backup_file, source_path="/foo").resolve_source_path()

    def test_invalid_backup_file(self):
        invalid = os.path.join(self.dir, "invalid.tar.gz")
        with open(invalid, "w") as f:
            f.write("no tar")

        with self.assertRaises(ValueError) as err:
            self._recovery(invalid, source_path="/foo").resolve_source_path()

        self.assertIn("can't be read as tar archive", str(err.exception))

    def test_source_path_command(self):
        backup_file = _create_backup_file(self.dir, MULTI_MOUNT_FILES, roots=MULTI_MOUNT_ROOTS)
        recovery = self._recovery(backup_file, "/restore", "/foo/config/")

        recovery.resolve_source_path()

        self.assertEqual(["tar", "-x", "-z", "-v", "-f", "/backup/backup.tar.gz", "--strip-components=2", "-C",
                          "/restore", "foo/config"], recovery._create_tar_cmd())

    def test_source_path_file_command(self):
        backup_file = _create_backup_file(self.dir, MULTI_MOUNT_FILES, roots=MULTI_MOUNT_ROOTS)
        recovery = self._recovery(backup_file, "/restore", "/foo/x.conf")

        recovery.resolve_source_path()

        self.assertEqual("--strip-components=1", recovery._create_tar_cmd()[6])
        self.assertEqual("foo/x.conf", recovery._create_tar_cmd()[-1])

    def test_source_path_with_dot_prefix_in_backup_file(self):
        backup_file = _create_backup_file(self.dir, MULTI_MOUNT_FILES, roots=MULTI_MOUNT_ROOTS, dot_prefix=True)
        recovery = self._recovery(backup_file, "/restore", "/foo/data")

        recovery.resolve_source_path()

        self.assertEqual("--strip-components=3", recovery._create_tar_cmd()[6])
        self.assertEqual("./foo/data", recovery._create_tar_cmd()[-1])

    def test_target_path_trailing_slash_is_removed(self):
        recovery = self._recovery("/backup/foo.tar.gz", "/foo/data/")
        self.assertEqual("/foo/data", recovery.target_path)
        self.assertEqual(2, recovery._determine_strip_length())

    @skipIf(shutil.which("tar") is None, "tar not available")
    def test_restore_each_mount_into_own_volume(self):
        """run the created tar commands with tar of the host: each mount ends up alone in its volume"""
        for compression in ("gz", "bz2"):
            backup_file = _create_backup_file(self.dir, MULTI_MOUNT_FILES, compression=compression,
                                              roots=MULTI_MOUNT_ROOTS)
            expected = {"/foo/data": {"a": "a", "sub/s": "s"}, "/foo/config": {"b": "b"}, "/bar/log": {"c": "c"},
                        "/foo/x.conf": {"x.conf": "x"}}

            for source_path, content in expected.items():
                with self.subTest(compression=compression, source_path=source_path):
                    volume = tempfile.mkdtemp(dir=self.dir)
                    recovery = self._recovery(backup_file, "/volume", source_path)
                    recovery.resolve_source_path()

                    cmd = recovery._create_tar_cmd()
                    cmd[cmd.index("-f") + 1] = backup_file
                    cmd[cmd.index("-C") + 1] = volume
                    subprocess.run(cmd, check=True, capture_output=True)

                    restored = {}
                    for root, _, files in os.walk(volume):
                        for file in files:
                            full = os.path.join(root, file)
                            with open(full) as f:
                                restored[os.path.relpath(full, volume)] = f.read()

                    self.assertEqual(content, restored)

    @skipIf(shutil.which("tar") is None, "tar not available")
    def test_restore_single_mount_without_source_path_as_before(self):
        backup_file = _create_backup_file(self.dir, {"/foo/data/a": "a", "/foo/data/sub/s": "s"},
                                          roots=["/foo/data"])
        volume = tempfile.mkdtemp(dir=self.dir)
        recovery = self._recovery(backup_file, "/volume/data")
        recovery.resolve_source_path()

        cmd = recovery._create_tar_cmd()
        cmd[cmd.index("-f") + 1] = backup_file
        cmd[cmd.index("-C") + 1] = volume
        subprocess.run(cmd, check=True, capture_output=True)

        self.assertEqual(["a", "sub"], sorted(os.listdir(volume)))


def _find_output(volume_dir, target_path):
    """output of `find <target_path> -mindepth 1` in a container that has the volume mounted at target_path"""
    entries = []
    for root, dirs, files in os.walk(volume_dir):
        for name in dirs + files:
            relative = os.path.relpath(os.path.join(root, name), volume_dir)
            entries.append(f"{target_path}/{relative}")
    return "\n".join(sorted(entries))


class TestCheckRecovery(TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        patcher = patch("builtins.print")
        self.mock_print = patcher.start()
        self.addCleanup(patcher.stop)

    def _restore(self, backup_file, target_path, source_path=None):
        """restore with the tar command of Recovery and tar of the host. :return: recovery, volume directory"""
        recovery = Recovery(backup_file=backup_file, docker_volume="foo_data", target_path=target_path,
                            source_path=source_path)
        recovery.resolve_source_path()
        volume = tempfile.mkdtemp(dir=self.dir)

        cmd = recovery._create_tar_cmd()
        cmd[cmd.index("-f") + 1] = backup_file
        cmd[cmd.index("-C") + 1] = volume
        subprocess.run(cmd, check=True, capture_output=True)

        return recovery, volume

    def _check(self, recovery, volume):
        with patch.object(Recovery, "_exec_docker_run", return_value=_find_output(volume, recovery.target_path)):
            return recovery.check_recovery()

    def test_create_list_cmd(self):
        recovery = Recovery(backup_file="/backup/path/foo.xyz.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz/to/the/file")

        self.assertEqual(["find", "/foo/bar/baz/to/the/file", "-mindepth", "1"], recovery._create_list_cmd())

    def test_expected_entries_of_legacy_fixture(self):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        self.assertEqual({"mosquitto.log", "mosquitto.db"}, recovery._determine_expected_entries())

    @patch("docker_volume_backup.container.recovery.docker.run", return_value="/foo/bar/baz/mosquitto.log\n"
                                                                              "/foo/bar/baz/mosquitto.db")
    def test_check_recovery_successful(self, docker_run):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        self.assertTrue(recovery.check_recovery())
        self.mock_print.assert_called_with("Recovery successful. All 2 entries of the backup file are in the Docker "
                                           "volume.")

    @patch("docker_volume_backup.container.recovery.docker.run", return_value="/foo/bar/baz/mosquitto.log")
    def test_check_recovery_missing_entry(self, docker_run):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        with self.assertLogs("docker_volume_backup.container.recovery", level="ERROR") as log:
            self.assertFalse(recovery.check_recovery())

        self.assertIn("1 of 2 entries of the backup file are missing in Docker volume 'foo_data': mosquitto.db",
                      log.output[0])

    @patch("docker_volume_backup.container.recovery.docker.run", return_value="")
    def test_check_recovery_empty_volume(self, docker_run):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        with self.assertLogs("docker_volume_backup.container.recovery", level="ERROR"):
            self.assertFalse(recovery.check_recovery())

    @patch("docker_volume_backup.container.recovery.docker.run",
           return_value="/foo/bar/baz/mosquitto.log\n/foo/bar/baz/mosquitto.db\n/foo/bar/baz/already_there")
    def test_check_recovery_additional_entries_are_ignored(self, docker_run):
        recovery = Recovery(backup_file="tests/fixtures/tst-backup.tar.gz", docker_volume="foo_data",
                            target_path="/foo/bar/baz")

        self.assertTrue(recovery.check_recovery())

    @skipIf(shutil.which("tar") is None, "tar not available")
    def test_restored_volume_matches_for_each_target_depth(self):
        """the old check only matched for a target path with 2 components"""
        backup_file = _create_backup_file(self.dir, {"/foo/data/a": "a", "/foo/data/sub/s": "s"},
                                          roots=["/foo/data"])

        for target_path in ("/data", "/foo/data", "/var/lib/mysql", "/a/b/c/d"):
            with self.subTest(target_path=target_path):
                # same depth as the source for a restore without --sourcepath
                if target_path.count("/") != 2:
                    recovery, volume = self._restore(backup_file, target_path, source_path="/foo/data")
                else:
                    recovery, volume = self._restore(backup_file, target_path)

                self.assertTrue(self._check(recovery, volume))

    @skipIf(shutil.which("tar") is None, "tar not available")
    def test_restored_volume_matches_for_each_mount_of_multi_mount_backup(self):
        for compression in ("gz", "bz2"):
            backup_file = _create_backup_file(self.dir, MULTI_MOUNT_FILES, compression=compression,
                                              roots=MULTI_MOUNT_ROOTS)

            for source_path in MULTI_MOUNT_ROOTS:
                with self.subTest(compression=compression, source_path=source_path):
                    recovery, volume = self._restore(backup_file, "/volume", source_path)

                    self.assertTrue(self._check(recovery, volume))

    @skipIf(shutil.which("tar") is None, "tar not available")
    def test_restored_volume_matches_with_dot_prefix_in_backup_file(self):
        backup_file = _create_backup_file(self.dir, MULTI_MOUNT_FILES, roots=MULTI_MOUNT_ROOTS, dot_prefix=True)

        for source_path in ("/foo/data", "/foo/x.conf"):
            with self.subTest(source_path=source_path):
                recovery, volume = self._restore(backup_file, "/volume", source_path)

                self.assertTrue(self._check(recovery, volume))

    @skipIf(shutil.which("tar") is None, "tar not available")
    def test_missing_file_in_restored_volume_is_detected(self):
        backup_file = _create_backup_file(self.dir, MULTI_MOUNT_FILES, roots=MULTI_MOUNT_ROOTS)
        recovery, volume = self._restore(backup_file, "/volume", "/foo/data")
        os.remove(os.path.join(volume, "sub", "s"))

        with self.assertLogs("docker_volume_backup.container.recovery", level="ERROR") as log:
            self.assertFalse(self._check(recovery, volume))

        self.assertIn("1 of 3 entries", log.output[0])
        self.assertIn("sub/s", log.output[0])
