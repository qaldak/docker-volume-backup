import logging

from python_on_whales import docker, DockerException

from util import cfg

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
