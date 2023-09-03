from backup.validator import Validator
from helper.argparser import ArgParser
from helper.logger import Logger
from volume_backup import *

logger = logging.getLogger(__name__)


def foo():
    print(f"config.X = {__name__}, {cfg.hasWarnings}")
    cfg.hasWarnings = True

    print(f"config.X = {cfg.hasWarnings}")

    print("Foo")
    bar()

    print(f"config.X = {cfg.hasWarnings}")


def main(container, path, restart):
    logger.info(f"Start volume backup for container '{args.container}'")
    logger.debug(f"Container: {container}, Backup path: {path}")

    # get directory for volume backup
    backup_dir = Validator.set_backup_dir(path, container)

    # create backup directory
    print(f"Backup dir: {backup_dir}")

    # check Docker volume is available

    # check Docker container is running
    # if restart: stop docker container

    # run docker backup

    # check docker backup

    # send notification

    print(f"path: {path}, restart: {restart}")

    foo()

    if container == "a":
        return "Foo"
    else:

        return "Bar"

    logger.info(f"Volume backup for container '{args.container}' completed successfully")


if __name__ == "__main__":
    args = ArgParser.parse_cli_args()
    Logger.init_logger(args.loglevel)

    print(args)
    main(args.container, args.path, args.restart)
