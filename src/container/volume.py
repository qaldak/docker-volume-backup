import logging

from python_on_whales import DockerClient, DockerException

docker = DockerClient()
logger = logging.getLogger(__name__)


class Volume:
    def __init__(self, container_name):
        self.name = container_name + "Volume"  # Todo: check

    def exists(self) -> bool:
        try:
            if docker.volume.exists(str(self.name)):
                return True

            return False

        except DockerException as err:
            logger.error("Foo", err)
