import logging

from python_on_whales import docker

logger = logging.getLogger(__name__)


class Container:
    def __init__(self, name: str):
        self.name = name
        self.isRunning = False
        self.hasVolume = False

    def exists(self) -> bool:
        if docker.container.exists(str(self.name)):
            logger.debug(f"Container '{self.name}' found")
            return True

        logger.debug(f"Container '{self.name}' not found")
        return False
