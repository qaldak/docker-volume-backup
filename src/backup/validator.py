import logging

from helper import cfg

logger = logging.getLogger(__name__)


class Validator:
    @staticmethod
    def set_backup_dir(path, container):
        logger.debug(f"Backup path: {path}, Container: {container}")
        if path is None:
            path = cfg.backup_path

        if path[-1] != "/":
            print("Foo")
            path = path + "/" + container

        return path
