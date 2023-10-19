import logging
import os

import docker
from _socket import gethostname

from util import cfg

logger = logging.getLogger(__name__)


class BackupDir:

    def __init__(self, path, container: str):
        """
        initialize backup directory

        :param path:
        :param container:
        """
        self.path = BackupDir.__set(path, container)

    @staticmethod
    def __set(path, container):
        logger.debug(f"Backup path: {path}, Container: {container}")
        if path is None:
            path = cfg.backup_path

        if path is None or path == "":
            raise ValueError(f"Invalid path defined: '{path}'")

        if path[-1] != "/":
            path = path + "/"

        path = path + container
        logger.debug(f"Backup directory set: {path}")

        return path

    def create(self):
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
            # Todo: notify and exit
            raise Exception(err)

        return


class LocalHost:
    @staticmethod
    def get_hostname():
        return gethostname().lower()

    @staticmethod
    def get_hostname_upper():
        return gethostname().upper()

    @staticmethod
    def is_docker_daemon_running() -> bool:  # Todo: unittest
        try:
            client = docker.from_env()
            client.ping()
        except docker.errors.DockerException as err:
            logger.error(f"Docker daemon not running on {LocalHost.get_hostname()}, {err}")
            raise docker.errors.DockerException(f"Docker daemon not running on {LocalHost.get_hostname()}.", err)
        except Exception as err:
            logger.error(f"Error while checking Docker daemon on {LocalHost.get_hostname()}, {err}")
            return False

        return True
