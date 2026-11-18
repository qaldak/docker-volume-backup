import logging

from python_on_whales import docker, DockerException

from docker_volume_backup.util import cfg

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
            logger.error(f"Error check volume exists: {err}")
            raise

    def containers(self, running_only: bool = False) -> list[str]:
        """
        :param running_only: only running containers
        :return: names of the containers that mount the volume (list[str])
        """
        try:
            containers = docker.container.list(all=not running_only, filters=[("volume", str(self.name))])
            names = sorted(container.name for container in containers)
            logger.debug(f"Containers using Docker volume '{self.name}' (running only: {running_only}): {names}")
            return names

        except DockerException as err:
            logger.error(f"Error determine containers of volume: {err}")
            raise

    def create(self) -> str:
        """
        :return: name of the created volume
        """
        try:
            new_volume = docker.volume.create(volume_name=self.name)
            if docker.volume.exists(str(new_volume)):
                logger.info(f"Volume '{str(new_volume)}' successfully created.")
                return str(new_volume)

            else:
                err = f"Error: volume '{str(new_volume)}' created, but not exists."
                logger.error(err)
                raise AttributeError(err)

        except DockerException as err:
            cfg.hasError = True
            cfg.errorMsg = err

            logger.error(err)
            raise
