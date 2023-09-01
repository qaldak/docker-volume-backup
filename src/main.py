# main.py

import argparse
import logging
import os

import config
from volume_backup import *


def parse_cli_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("container", help="Define Docker container whose volume should be backed up")
    parser.add_argument("-p", "--path",
                        help="Backup destination path (Default by ENV settings)")  # Todo: Default Path from ENV file
    parser.add_argument("-r", "--restart", action="store_true", dest="restart",
                        help="Stops Docker container for backup and restart when done")
    parser.add_argument("--debug", action="store_const", dest="loglevel", const=logging.DEBUG, default=logging.DEBUG,
                        help="Set loglevel to DEBUG")
    return parser.parse_args()


def init_logger():
    logdir = "log"
    if not os.path.isdir(logdir):
        os.makedirs(logdir)

    # Todo: funcName vs name
    logging.basicConfig(level=args.loglevel, filename=f"{logdir}/docker-volume-backup.log",
                        format='%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')


logger = logging.getLogger(__name__)


def foo():
    config.x += 1
    print(f"config.X = {config.x}")
    print("Foo")
    bar()


def main(container, path, restart):
    logger.info(f"Start volume backup for container '{args.container}'")
    logger.debug(f"Container: {container}, Backup path: {path}")

    if path is None:
        path = "/home/roger/temp"

    print(f"path: {path}, restart: {restart}")

    foo()

    if container == "a":
        return "Foo"
    else:

        return "Bar"

    logger.info(f"Volume backup for container '{args.container}' completed successfully")


if __name__ == "__main__":
    args = parse_cli_args()
    init_logger()

    main(args.container, args.path, args.restart)
