import logging

from util import cfg

logger = logging.getLogger(__name__)


def set_backup_dir(path, container):
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
