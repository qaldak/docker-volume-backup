from docker.container import Container
from util.accessor import set_backup_dir
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


def main(container, path, restart):
    logger.info(f"Start volume backup for container '{args.container}'")
    logger.debug(f"Container: {container}, Backup path: {path}")

    # check container exists
    if not Container.validate_container_exists(container):
        logger.debug(f"Container '{container}' not found on ''")  # Todo: get_hostname()

    # get directory for volume docker
    backup_dir = set_backup_dir(path, container)

    # create docker directory
    print(f"Backup dir: {backup_dir}")

    # check Docker volume is available

    # check Docker container is running
    # if restart: stop docker container

    # run docker docker

    # check docker docker

    # send notification

    print(f"path: {path}, restart: {restart}")

    # foo()

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
