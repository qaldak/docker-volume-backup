import logging

from python_on_whales import docker

logger = logging.getLogger(__name__)


class Container:

    @staticmethod
    def validate_container_exists(container: str) -> bool:
        if docker.container.exists(container):
            logger.debug(f"Container '{container}' found")
            return True

        logger.debug(f"Container '{container}' not found")
        return False
