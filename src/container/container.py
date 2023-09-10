import logging

from python_on_whales import docker

logger = logging.getLogger(__name__)


class Container:
    def __init__(self, name: str):
        self.name = name
        self.id = ""
        self.isRunning = False
        self.hasVolume = False

    def exists(self) -> bool:
        if docker.container.exists(str(self.name)):
            self.id = str(docker.container.inspect(x=self.name))
            logger.debug(f"Container '{self.name}' found with id '{self.id}'")
            return True

        logger.debug(f"Container '{self.name}' not found")
        return False

    def determine_volume(self):
        docker.client_config.docker_cmd()
        pass
