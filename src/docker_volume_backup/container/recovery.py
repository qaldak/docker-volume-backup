import os
import posixpath
import tarfile
import warnings

from python_on_whales import DockerException, docker

from docker_volume_backup.container.volume import logger
from docker_volume_backup.util.accessor import Compression, FileExtension


class Recovery:

    def __init__(self, backup_file, docker_volume, target_path, source_path=None):
        """
        :param backup_file: backup file (tar archive) to restore
        :param docker_volume: Docker volume to restore into
        :param target_path: path in the container where the volume is mounted for the restore
        :param source_path: (optional) path of a mount in the backup file to restore, e.g. "/foo/data". A backup file
            contains all mounts of a container. Can be omitted if the backup file contains only one mount.
        """
        self.backup_file = backup_file
        self.backup_path = os.path.dirname(backup_file)
        self.container_backup_file = os.path.basename(backup_file)
        self.docker_volume = docker_volume
        self.target_path = str(target_path).rstrip("/") or str(target_path)
        self.source_path = source_path
        self._source = None  # restore source in the backup file (set by resolve_source_path)
        self._source_stored_name = None  # name of the source as stored in the tar file
        self._source_is_file = False
        self._source_has_dot_prefix = False

    @staticmethod
    def _normalize_member_name(name: str) -> str:
        """
        :return: member name of a tar file without leading "./" or "/" and without trailing "/"
        """
        normalized = posixpath.normpath(str(name)).lstrip("/")
        return "" if normalized == "." else normalized

    def _read_archive(self) -> tuple[dict[str, bool], bool]:
        """
        :return: 1. all members of the backup file: normalized name -> is file, 2. names stored with leading "./"
        """
        try:
            with tarfile.open(self.backup_file, "r") as tar:
                tar_members = tar.getmembers()

        except (tarfile.TarError, OSError) as err:
            raise ValueError(f"Backup file '{self.backup_file}' can't be read as tar archive: {err}") from err

        members = {}
        for member in tar_members:
            name = self._normalize_member_name(member.name)
            if name:
                members[name] = member.isfile()

        return members, any(member.name.startswith("./") for member in tar_members)

    @staticmethod
    def _determine_archive_roots(names) -> list[str]:
        """
        A backup file contains one path per mount of the container. These roots are the members without a
        parent member.

        :return: sorted list of the paths of the mounts in the backup file
        """
        names = set(names)
        roots = []

        for name in names:
            parent = posixpath.dirname(name)
            while parent and parent not in names:
                parent = posixpath.dirname(parent)

            if not parent:
                roots.append(name)

        return sorted(roots)

    def resolve_source_path(self):
        """
        Determine which part of the backup file is restored. Must be called before restoring.

        - source path given: it has to be contained in the backup file, only this part is restored.
        - no source path and backup file with one mount: whole backup file is restored (as always).
        - no source path and backup file with several mounts: restoring all of them into one volume would mix up
          their content, so the restore is rejected.

        :raise ValueError: if the source path is not part of the backup file or has to be specified
        """
        members, has_dot_prefix = self._read_archive()
        roots = self._determine_archive_roots(members)
        available = ", ".join(f"/{root}" for root in roots)

        if self.source_path:
            source = self._normalize_member_name(self.source_path)

            if source not in members:
                raise ValueError(f"Source path '{self.source_path}' not found in backup file "
                                 f"'{self.backup_file}'. Available paths: {available}")

            self._source = source
            self._source_is_file = members[source]
            self._source_has_dot_prefix = has_dot_prefix
            self._source_stored_name = f"./{source}" if has_dot_prefix else source
            logger.debug(f"Restore source path in backup file: {self._source_stored_name}")
            return

        if len(roots) > 1:
            raise ValueError(f"Backup file '{self.backup_file}' contains {len(roots)} paths: {available}. "
                             f"Specify the path to restore with --sourcepath.")

    def restore_volume_backup(self):
        print(f"Restoring Docker volume ... ")

        try:
            restore_cmd = self._create_tar_cmd()
            logger.debug(f"Restoring Docker volume. Command {restore_cmd}")
            self._exec_docker_run(restore_cmd)
            print("Docker volume restored.")

        except DockerException as err:
            logger.exception(err)
            raise

    def check_recovery(self):
        print(f"Comparing restored files with tar content ...")
        try:
            volume_file_count = self._exec_docker_run(self._create_list_cmd())
            tar_file_count = self._determine_tar_file_content()

            logger.debug(f"Content Docker volume: {volume_file_count}, Content tar file: {tar_file_count}")

            if int(volume_file_count) != tar_file_count:
                warn_msg = f"Number of restored files does not match the content of tar file: {volume_file_count} vs {tar_file_count}. Check manually or run again in debug mode for more details."
                logger.warning(warn_msg)
                warnings.warn(warn_msg)
            else:
                print(f"Recovery successful. Number of restored files matches: {volume_file_count} vs {tar_file_count}")

        except ValueError as err:
            print(f"Error occurred: {err}")
            raise

    def _determine_tar_file_content(self) -> int:
        with tarfile.open(self.backup_file, 'r') as tar:
            names = tar.getnames()

        if self._source:
            names = [name for name in names
                     if self._normalize_member_name(name) == self._source
                     or self._normalize_member_name(name).startswith(f"{self._source}/")]

        counter = len(names)
        logger.debug(f"tar file content: {counter}, list: {names}")
        return counter

    def _create_list_cmd(self) -> list[str]:
        base_dir = "/" + str(self.target_path).split("/")[1]
        list_cmd = ["ash", "-c", f"find {base_dir} -mindepth 1 | wc -l"]
        logger.debug(f"created list command: {list_cmd}")
        return list_cmd

    def _create_tar_list_cmd(self) -> list[str]:
        # t?vf /backup/fedora-mosquitto_fedora-volume-backup.tar.gz | wc -l
        cmp_method = self._determine_cmp_method()
        tar_cmd = ["ash", "-c",
                   f"tar -t {cmp_method} -v -f /backup/{self.container_backup_file} | wc -l"]
        logger.debug(f"command for tar list content: {tar_cmd}")
        return tar_cmd

    def _create_tar_cmd(self) -> list[str]:
        cmp_method = self._determine_cmp_method()
        tar_cmd = ["tar", "-x", f"{cmp_method}", "-v", "-f", f"/backup/{self.container_backup_file}",
                   f"--strip-components={self._determine_strip_length()}", "-C", f"{self.target_path}"]

        if self._source:
            tar_cmd.append(self._source_stored_name)

        logger.debug(f"command for restoring from tar: {tar_cmd}")
        return tar_cmd

    def _determine_strip_length(self) -> int:
        if self._source:
            # the content of the source lands directly in the target path: remove the path of the source
            # (and the leading "./", if stored). A single file keeps its name.
            strip_length = self._source.count("/") + (0 if self._source_is_file else 1)
            return strip_length + (1 if self._source_has_dot_prefix else 0)

        return str(self.target_path).count("/")

    def _determine_cmp_method(self) -> str:
        file_extension = os.path.splitext(self.backup_file)[1]
        logger.debug(f"file extension: {file_extension}")
        return Compression[FileExtension(file_extension).name].value  # Todo: move to accessor?

    def _exec_docker_run(self, cmd: list[str]):
        volume_mapping = [{f"{self.docker_volume}:{self.target_path}"}, {f"{self.backup_path}:/backup"}]
        logger.debug(f"volume mapping: {volume_mapping}")

        return docker.run("busybox:latest", cmd, remove=True, volumes=volume_mapping, detach=False)
