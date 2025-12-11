import logging
import os
import time

from python_on_whales import docker, DockerException

from docker_volume_backup.util import cfg
from docker_volume_backup.util.accessor import LocalHost, calc_duration, Compression, FileExtension

logger = logging.getLogger(__name__)


class Backup:

    def __init__(self, container, backup_dir):
        """
        initalize Backup object

        :param container:
        :param backup_dir:
        """
        self.backup_dir = backup_dir
        self.container = container
        self.backup_file = self._get_backup_filepath()
        self.new_user_id = os.getenv("BACKUP_FILE_OWNER")
        self.new_group_id = os.getenv("BACKUP_FILE_GROUP")
        self.new_file_perms = os.getenv("BACKUP_FILE_PERMS")
        self.volume_mapping = [{f"{self.backup_dir.path}:/backup"}]

    @staticmethod
    def _determine_compression_method() -> tuple[str, str]:
        """
        determine compression method for tar command and associated file extensions according to .env settings.

        :return: 1. compression method, 2. file extension (tuple[str, str])
        """
        try:
            logger.debug(f"Defined compression method: {os.getenv('COMPRESSION_METHOD')}")

            if not os.getenv("COMPRESSION_METHOD"):
                logger.debug(
                    f"Compression method undefined or empty. Return '{Compression.GZIP.value}'")
                return Compression.GZIP.value, FileExtension.GZIP.value

            return Compression[os.getenv("COMPRESSION_METHOD")].value, FileExtension[
                os.getenv("COMPRESSION_METHOD")].value

        except KeyError:
            logger.warning(
                f"Compression method not defined properly: {os.getenv('COMPRESSION_METHOD')}. "
                f"Using '{Compression.GZIP.value}'")
            return Compression.GZIP.value, FileExtension.GZIP.value

        except Exception as err:
            logger.error(err)
            raise

    def _create_tar_cmd(self) -> list[str]:
        """
        creates a tar command to back up all determined volumes and bindings of the input container.

        :return: tar command to execute (list[str])
        """

        cmp_method, file_ext = self._determine_compression_method()
        backup_filepath = self._get_backup_filepath()

        tar_cmd = ["tar", "c", f"{cmp_method}", "-f",
                   f"{backup_filepath}"]

        for volume in self.container.docker_volumes:
            tar_cmd.append(f"{volume}")
            logger.debug(f"Add volume {volume} to tar command")

        for binding in self.container.docker_bindings:
            tar_cmd.append(f"{binding}")
            logger.debug(f"Add binding {binding} to tar command")

        logger.debug(f"tar command created: {tar_cmd}")
        return tar_cmd

    def _exec_docker_run(self, cmd: list[str]):
        logger.debug("Execute docker run command")
        logger.debug(cmd)
        logger.debug(self.container.name)
        return docker.run("busybox:latest", cmd, remove=True, volumes_from=[self.container.name],
                          volumes=self.volume_mapping, detach=False)

    def _get_backup_filename(self) -> str:
        """
        calc backup filename with correct extension according env settings

        :return: string of backup file name
        """
        cmp_method, file_ext = self._determine_compression_method()
        backup_file = f"{LocalHost.get_hostname()}-{self.container.name}-volume-backup.tar{file_ext}"

        cfg.backup_file = backup_file
        return backup_file

    def _get_backup_filepath(self) -> str:
        """
        calc backup file path

        :return: string of backup file path
        """
        return f"/backup/{self._get_backup_filename()}"

    def _get_backup_file_size(self) -> int:
        """
        :return: size of backup file in bytes (from host)
        """
        backup_file_host = f"{self.backup_dir.path}/{self._get_backup_filename()}"
        logger.debug(f"Backup file size on host: {backup_file_host}, size: {os.path.getsize(backup_file_host)}")
        try:
            return os.path.getsize(backup_file_host)

        except FileNotFoundError as err:
            logger.error(f"Not able to determine file size. Backup file not found: {backup_file_host}, Error: {err}")
            cfg.hasError = True
            cfg.errorMsg = err

    def change_file_ownership(self):
        """
        Changes file ownership according to .env settings by running a Docker container.
        Execution via Docker to provide the required permissions.
        """
        logger.debug(f"UserId = '{self.new_user_id}', GroupId = '{self.new_group_id}'")
        if not self.new_group_id:
            new_ownership = self.new_user_id
        elif not self.new_user_id:
            new_ownership = self.new_group_id
        else:
            new_ownership = f"{self.new_user_id}:{self.new_group_id}"

        chown_cmd = ["chown", f"{new_ownership}", f"{self.backup_file}"]

        try:
            tmp = self._exec_docker_run(chown_cmd)

            logger.debug(f"Return value running backup: {tmp}")
            logger.info(f"chown command run successful.")

        except DockerException as err:
            logger.exception(err)
            raise

        except Exception as err:
            logger.exception(err)
            raise

    def change_file_permissions(self):
        """
        Changes file permissions according to .env settings by running a Docker container.
        Execution via Docker to provide the required permissions.
        """
        logger.debug(f"new permissions: '{self.new_file_perms}'")

        chmod_cmd = ["chmod", f"{self.new_file_perms}", f"{self.backup_file}"]

        try:
            tmp = self._exec_docker_run(chmod_cmd)

            logger.debug(f"Return value running backup: {tmp}")
            logger.info(f"chmod command run successful.")

        except DockerException as err:
            logger.exception(err)
            raise

        except Exception as err:
            logger.exception(err)
            raise

    def run_backup(self):
        """
        backup all volumes and bindings of input container to a tar-file in the backup-directory.
        """

        logger.debug(
            f"Start backup for volumes {self.container.docker_volumes} and bindings {self.container.docker_bindings}")
        logger.debug(f"Backup path: {self.backup_dir.path}")

        if not self.container.has_docker_volume and not self.container.has_docker_bindings:
            raise AssertionError("No volumes to backup")

        tar_cmd = self._create_tar_cmd()

        # Todo: check issue when running on windows?
        volume_mapping = [{
            f"{self.backup_dir.path}:/backup"
        }]
        logger.debug(f"volume mapping for backup container: {volume_mapping}")

        try:
            logger.info(f"Execute Volume backup for container '{self.container.name}'. tar command: {tar_cmd}")
            cfg.backup_start_time = int(time.time())

            tmp = self._exec_docker_run(tar_cmd)

            cfg.backup_size = self._get_backup_file_size()
            cfg.backup_end_time = int(time.time())
            logger.debug(f"Return value running backup: {tmp}")
            logger.info(f"Volume backup for container '{self.container.name}' successful. Duration: "
                        f"{calc_duration(cfg.backup_start_time, cfg.backup_end_time)}, "
                        f"Backup size: {cfg.backup_size}")

        except DockerException as err:
            logger.exception(err)
            raise

        except Exception as err:
            logger.exception(err)
            raise

    def should_change_filesettings(self) -> tuple[bool, bool]:
        """
        determines if file ownership or file settings should change according .env settings.

        :return: should_change_ownership (boolean), should_change_permissions (boolean)
        """
        should_change_ownership = False
        should_change_permissions = False

        if self.new_user_id or self.new_group_id:
            logger.debug(f"new file ownership defined: user = {os.getenv('BACKUP_FILE_OWNER')}, "
                         f"group = {os.getenv('BACKUP_FILE_GROUP')}")
            should_change_ownership = True

        if self.new_file_perms:
            logger.debug(f"new file permissions defined: {os.getenv('BACKUP_FILE_PERMS')}")
            should_change_permissions = True

        logger.debug(f"should change filesettings: change owner: {should_change_ownership}, "
                     f"change permission: {should_change_permissions}")
        return should_change_ownership, should_change_permissions
