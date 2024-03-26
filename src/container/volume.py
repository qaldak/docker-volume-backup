import logging
import os

from python_on_whales import docker, DockerException

from util import cfg
from util.accessor import Compression, FileExtension

logger = logging.getLogger(__name__)


class Volume:
    def __init__(self, volume_name):
        self.name = volume_name

    def exists(self) -> bool:
        try:
            if docker.volume.exists(str(self.name)):
                return True

            return False

        except DockerException as err:
            logger.error("Error check volume exists.", err)
            raise

    def in_use(self) -> bool:
        try:
            volume_list = docker.volume.list(filters=dict(dangling=0, driver="local", name=str(self.name)))
            if len(volume_list) > 0:
                logger.debug(f"Docker volume '{self.name}' in use: {volume_list}")
                return True

            logger.debug(f"Docker volume '{self.name}' not in use.")
            return False

        except DockerException as err:
            logger.error("Error check volume is in use.", err)
            raise

    def create(self):
        try:
            new_volume = docker.volume.create(volume_name=self.name)
            if docker.volume.exists(str(new_volume)):
                logger.info(f"Volume '{str(new_volume)}' successfully created.")

            else:
                err = f"Error: volume '{str(new_volume)}' created, but not exists."
                logger.error(err)
                raise AttributeError(err)

        except DockerException as err:
            cfg.hasError = True
            cfg.errorMsg = err

            logger.error(err)
            raise


class Recovery:

    def __init__(self, backup_file, docker_volume, target_path):
        self.backup_file = backup_file
        self.backup_path = os.path.dirname(backup_file)
        self.container_backup_file = os.path.basename(backup_file)
        self.docker_volume = docker_volume
        self.target_path = target_path

    def restore_volume_backup(self):
        try:
            restore_cmd = self._create_tar_cmd()
            print(restore_cmd)

            self._exec_docker_run(restore_cmd)

        except DockerException as err:
            logger.exception(err)
            raise

    def check_recovery(self):
        file_counter = self._exec_docker_run(self._create_list_cmd())
        print(file_counter)

        tar_file_counter = self._exec_docker_run(self._create_tar_list_cmd())
        print("Bar: ", tar_file_counter)

    def _create_list_cmd(self) -> list[str]:
        base_dir = "/" + str(self.target_path).split("/")[1]
        list_cmd = ["ash", "-c", f"find {base_dir} -mindepth 1"]
        print(list_cmd)
        return list_cmd

    def _create_tar_list_cmd(self) -> list[str]:
        # t?vf /backup/fedora-mosquitto_fedora-volume-backup.tar.gz | wc -l
        cmp_method = self._determine_cmp_method()
        tar_cmd = ["ash", "-c", f"tar -t {cmp_method} -v -f /backup/{self.container_backup_file}"]
        return tar_cmd

    def _create_tar_cmd(self) -> list[str]:
        cmp_method = self._determine_cmp_method()
        tar_cmd = ["tar", "-x", f"{cmp_method}", "-v", "-f", f"/backup/{self.container_backup_file}",
                   f"--strip-components={self._determine_strip_length()}", "-C", f"{self.target_path}"]
        return tar_cmd

    def _determine_strip_length(self) -> int:
        return str(self.target_path).count("/")

    def _determine_cmp_method(self) -> str:
        file_extension = os.path.splitext(self.backup_file)[1]
        return Compression[FileExtension(file_extension).name].value  # Todo: move to accessor?

    def _exec_docker_run(self, cmd: list[str]):
        volume_mapping = [{f"{self.docker_volume}:{self.target_path}"}, {f"{self.backup_path}:/backup"}]
        print(f"Volume mapping: {volume_mapping}")
        print(f"Command: {cmd}")

        return docker.run("busybox:latest", cmd, remove=True, volumes=volume_mapping, detach=False)
