import logging

from python_on_whales import docker, DockerException

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
            return docker.volume.create(volume_name=self.name)

        except DockerException as err:
            logger.error(err)
            raise
