import logging
import os

import docker
from _socket import gethostname

logger = logging.getLogger(__name__)


class BackupDir:

    def __init__(self, path):
        """
        initialize backup directory

        :param path:
        """
        self.path = BackupDir.__set(path)

    @staticmethod
    def __set(path):
        logger.debug(f"Backup path by command line: {path}")

        if not path:
            if not os.getenv("BACKUP_DIR"):
                raise ValueError(f"Invalid backup path defined: '{path}'")

            path = os.getenv("BACKUP_DIR")

        logger.debug(f"Backup directory set: {path}")

        return path

    def create(self):
        """
        Checks whether backup directory already exists. If not, create it.
        """
        if os.path.isdir(self.path):
            logger.debug(f"Backup directory already exists: {self.path}")
            return

        try:
            os.makedirs(self.path, 0o777)
            logger.info(f"Backup directory created: {self.path}")

        except FileExistsError as err:
            msg = f"Backup directory '{self.path}' exists. {err}"
            logger.info(msg)

        except Exception as err:
            logger.error(f"Error creating backup directory: {self.path}, {err}")
            raise

        return


class LocalHost:
    @staticmethod
    def get_hostname() -> str:
        """
        :return: hostname in lowercase
        """
        return gethostname().lower()

    @staticmethod
    def get_hostname_upper() -> str:
        """
        :return: hostname in uppercase
        """
        return gethostname().upper()

    @staticmethod
    def is_docker_daemon_running() -> bool:
        """
        Determines whether Docker daemon is running on the local host.
        Raises an exception on DockerException.

        :return: True if running, False if error occurred
        """
        try:
            client = docker.from_env()
            client.ping()

        except docker.errors.DockerException as err:
            logger.error(f"Docker daemon not running on {LocalHost.get_hostname()}, {err}")
            raise

        except Exception as err:
            logger.error(f"Error while checking Docker daemon on {LocalHost.get_hostname()}, {err}")
            return False

        return True
