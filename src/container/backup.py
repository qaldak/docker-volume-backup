import logging
import os
from enum import Enum

from python_on_whales import docker, DockerException

from util.accessor import LocalHost

logger = logging.getLogger(__name__)


def __determine_compression_method() -> tuple[str, str]:
    try:
        logger.debug(f"Defined compression method: {os.getenv('COMPRESSION_METHOD')}")

        if not os.getenv("COMPRESSION_METHOD"):
            logger.debug(
                f"Compression method undefined or empty. Return '{Compression.GZIP.value}'")
            return Compression.GZIP.value, FileExtension.GZIP.value

        return Compression[os.getenv("COMPRESSION_METHOD")].value, FileExtension[os.getenv("COMPRESSION_METHOD")].value

    except KeyError as err:
        logger.warning(
            f"Compression method not defined properly: {os.getenv('COMPRESSION_METHOD')}. Using '{Compression.GZIP.value}'")
        return Compression.GZIP.value, FileExtension.GZIP.value

    except Exception as err:
        logger.error(err)
        raise


def create_tar_cmd(container) -> list[str]:
    """
    creates a tar command to back up all determined volumes and bindings of the input container.

    :param container:
    :return: tar command to execute
    """

    cmp_method, file_ext = __determine_compression_method()

    tar_cmd = ["tar", "c", f"{cmp_method}", "-f",
               f"/backup/{LocalHost.get_hostname()}-{container.name}-volume-backup.tar{file_ext}"]

    for volume in container.docker_volumes:
        tar_cmd.append(f"{volume}")
        logger.debug(f"Add volume {volume} to tar command")

    for binding in container.docker_bindings:
        tar_cmd.append(f"{binding}")
        logger.debug(f"Add binding {binding} to tar command")

    logger.debug(f"tar command created: {tar_cmd}")
    return tar_cmd


class Volume:

    @staticmethod
    def run_backup(container, backup_dir):
        """
        backup all volumes and bindings of input container to a tar-file in the backup-directory.

        :param container:
        :param backup_dir:
        """

        logger.debug(f"Start backup for volumes {container.docker_volumes} and bindings {container.docker_bindings}")
        logger.debug(f"Backup path: {backup_dir.path}")

        if not container.has_docker_volume and not container.has_docker_bindings:
            raise AssertionError("No volumes to backup")

        tar_cmd = create_tar_cmd(container)

        # Todo: check issue when running on windows?
        volume_mapping = [{
            f"{backup_dir.path}:/backup"
        }]
        logger.debug(f"volume mapping for backup container: {volume_mapping}")

        try:
            logger.info(f"Execute Volume backup for container '{container.name}'. tar command: {tar_cmd}")

            tmp = docker.run("busybox:latest", tar_cmd, remove=True, volumes_from=container.name,
                             volumes=volume_mapping, detach=False)

            logger.debug(f"Return value running backup: {tmp}")
            logger.info(f"Volume backup for container '{container.name}' successful")

        except DockerException as err:
            logger.exception(err)
            raise

        except Exception as err:
            logger.exception(err)
            raise


class Compression(Enum):
    BZIP2 = "-j"
    GZIP = "-z"  # default


class FileExtension(Enum):
    BZIP2 = ".bz2"
    GZIP = ".gz"
