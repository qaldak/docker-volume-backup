import logging

from python_on_whales import docker, DockerException

from util import cfg

logger = logging.getLogger(__name__)


class Volume:
    def __init__(self, container_name):
        self.name = container_name + "_data"  # Todo: check

    def exists(self) -> bool:
        try:
            if docker.volume.exists(str(self.name)):
                return True

            return False

        except DockerException as err:
            logger.error("Foo", err)

    def create(self) -> object:
        try:
            new_volume = docker.volume.create(volume_name=self.name)
            if docker.volume.exists(str(new_volume)):
                logger.info(f"Volume '{str(new_volume)}' successfully created.")
                return new_volume

            else:
                err = f"Error: volume '{str(new_volume)}' created, but not exists."
                logger.error(err)
                raise AttributeError(err)

        except DockerException as err:
            cfg.hasError = True
            cfg.errorMsg = err

            logger.error(err)
            raise
