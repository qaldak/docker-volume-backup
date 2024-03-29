import logging
import os
from _socket import gethostname
from datetime import datetime, timedelta
from enum import Enum

import docker

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


class EnvSettings:

    def __validate_chat_settings(self):
        if os.getenv("CHAT_ALERTING") in (Alerting.ALWAYS.name, Alerting.ON_FAILURE.name):
            if not os.getenv("CHAT_SERVICE") == Receiver.SLACK.name:
                err = "CHAT_ALERTING enabled but CHAT_SERVICE not correct. Check .env config."
                logger.error(err)
                raise ValueError(err)

            self.__validate_slack_settings()

    @staticmethod
    def __validate_slack_settings():
        if not (os.getenv("SLACK_CHANNEL_ID") and os.getenv("SLACK_AUTH_TOKEN")):
            err = "CHAT_SERVICE=SLACK but SLACK_CHANNEL_ID / SLACK_AUTH_TOKEN missing. Check .env config."
            logger.error(err)
            raise ValueError(err)

    @staticmethod
    def __validate_mqtt_settings():
        if os.getenv("MQTT_ALERTING") in (Alerting.ALWAYS.name, Alerting.ON_FAILURE.name):
            if not (os.getenv("MQTT_BROKER") and os.getenv("MQTT_PORT") and os.getenv("MQTT_TOPIC")):
                err = "MQTT_ALERTING enabled but MQTT config not correct. Check .env config."
                raise ValueError(err)

    def validate(self):
        self.__validate_chat_settings()
        self.__validate_mqtt_settings()
        return


class LocalHost:
    @staticmethod
    def get_hostname() -> str:
        """
        :return: hostname in lowercase
        """
        return gethostname().lower()

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


def calc_duration(start: int, end: int) -> timedelta:
    duration = datetime.fromtimestamp(end) - datetime.fromtimestamp(start)
    return duration


class Alerting(Enum):
    ALWAYS = 10
    ON_FAILURE = 20
    NEVER = 90
    UNDEFINED = 99


class Compression(Enum):
    BZIP2 = "-j"
    GZIP = "-z"  # default


class FileExtension(Enum):
    BZIP2 = ".bz2"
    GZIP = ".gz"


class Receiver(Enum):
    SLACK = 1
    MQTT = 80
    UNDEFINED = 99
