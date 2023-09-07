from docker.container import Container
from util.accessor import BackupDir
from util.argparser import ArgParser
from util.logger import Logger
from volume_backup import *

logger = logging.getLogger(__name__)


def foo():
    print(f"config.X = {__name__}, {cfg.hasWarnings}")
    cfg.hasWarnings = True

    print(f"config.X = {cfg.hasWarnings}")

    print("Foo")
    bar()

    print(f"config.X = {cfg.hasWarnings}")


def main(path, restart):
    logger.info(f"Start volume backup for container '{container.name}'")
    logger.debug(f"Container: {container.name}, Backup path: {path}")

    # check container exists
    if not container.exists():
        logger.debug(f"Container '{container.name}' not found on ''")  # Todo: get_hostname()

    # get directory for volume docker
    backup_dir = BackupDir(path, container.name)

    # create docker directory
    print(f"Backup dir: {backup_dir.path}")
    backup_dir.create()

    # check Docker volume is available

    # check Docker container is running
    # if restart: stop docker container

    # run docker docker

    # check docker docker

    # send notification

    print(f"path: {path}, restart: {restart}")

    # foo()

    if container.name == "a":
        return "Foo"
    else:

        return "Bar"

    logger.info(f"Volume backup for container '{args.container}' completed successfully")


if __name__ == "__main__":
    args = ArgParser.parse_cli_args()

    # initialize objects
    Logger.init_logger(args.loglevel)
    container = Container(args.container)

    logger.debug(f"Start volume backup with args '{args}'")

    main(args.path, args.restart)
