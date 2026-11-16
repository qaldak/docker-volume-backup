import logging
import os
import re
from socket import gethostname
from datetime import datetime, timedelta
from enum import Enum

import docker

logger = logging.getLogger(__name__)

DEFAULT_BASE_IMAGE = "busybox:latest"  # image of the helper container for backup and restore, if BASE_IMAGE is undefined
_IMAGE_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@-]*")


def get_base_image() -> str:
    """
    Image of the helper container for backup and restore: BASE_IMAGE from .env. The setting is read when it is
    needed, not at import: the .env file is loaded after the modules are imported.
    The image needs the commands tar, mv, rm, chown, chmod, find and sh.

    :return: image name, e.g. "busybox:latest" (default if BASE_IMAGE is undefined or empty)
    :raise ValueError: if BASE_IMAGE is not a valid image reference (e.g. contains spaces)
    """
    image = (os.getenv("BASE_IMAGE") or "").strip()

    if not image:
        return DEFAULT_BASE_IMAGE

    if not _IMAGE_REFERENCE.fullmatch(image):
        raise ValueError(f"BASE_IMAGE not defined properly: '{image}'. Image name expected, e.g. "
                         f"'{DEFAULT_BASE_IMAGE}' or 'alpine:3.20'. Check .env config.")

    return image


def parse_file_mode(value, default: int, name: str) -> int:
    """
    Parse a permission setting in octal notation, e.g. "640".

    :param value: setting from .env (None or empty: use default)
    :param default: mode to use if the setting is undefined or invalid
    :param name: name of the setting for the log message
    :return: file mode (int)
    """
    value = str(value).strip() if value else ""
    if not value:
        return default

    try:
        mode = int(value, 8)
        if not value.isdigit() or mode > 0o7777:
            raise ValueError("not an octal mode")
        return mode

    except ValueError:
        logger.warning(f"{name} not defined properly: '{value}'. Octal mode like '{default:o}' expected. "
                       f"Using default: '{default:o}'")
        return default


class BackupDir:
    DEFAULT_PERMS = 0o750  # permissions of a created backup directory, if BACKUP_DIR_PERMS is undefined or invalid

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
            perms = parse_file_mode(os.getenv("BACKUP_DIR_PERMS"), self.DEFAULT_PERMS, "BACKUP_DIR_PERMS")
            os.makedirs(self.path, perms)
            os.chmod(self.path, perms)  # makedirs mode is reduced by the umask
            logger.info(f"Backup directory created: {self.path}, permissions: {perms:o}")

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

    @staticmethod
    def __validate_base_image():
        try:
            get_base_image()

        except ValueError as err:
            logger.error(err)
            raise

    def validate(self):
        self.__validate_chat_settings()
        self.__validate_mqtt_settings()
        self.__validate_base_image()
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
        Raises an exception on DockerException (e.g. daemon not reachable).

        :return: True if running, False if another error occurred
        """
        try:
            client = docker.from_env(version="auto")
            logger.debug(f"Docker client API version: {client.api.api_version}")
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
