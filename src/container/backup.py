import logging

from python_on_whales import docker, DockerException

from util.accessor import LocalHost

logger = logging.getLogger(__name__)


def create_tar_cmd(container) -> list[str]:
    """
    creates a tar command to back up all determined volumes and bindings of the input container.

    :param container:
    :return: tar command to execute
    """

    tar_cmd = ["tar", "-czf", f"/backup/{LocalHost.get_hostname()}_{container.name}_volume_backup.tar.gz"]

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
