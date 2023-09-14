from container.container import Container
from util.accessor import BackupDir, LocalHost
from util.argparser import ArgParser
from util.logger import Logger
from volume_backup import *

logger = logging.getLogger(__name__)


def main(path, restart):
    logger.info(f"Start volume backup for container '{container.name}'")
    logger.debug(f"Container: {container.name}, Backup path: {path}")

    # Todo: check Docker daemon is running!
    # Todo: concept: where notification should be triggered, centralised vs decentralised

    print(LocalHost.is_docker_daemon_running())

    # check container exists
    if not container.exists():
        logger.debug(f"Container '{container.name}' not found on ''")  # Todo: get_hostname()

    print(LocalHost.get_hostname())

    # get directory for volume container
    backup_dir = BackupDir(path, container.name)

    # create container directory
    print(f"Backup dir: {backup_dir.path}")
    backup_dir.create()

    # determine Docker volume of container
    has_volumes_to_backup = container.determine_volume
    if not has_volumes_to_backup:
        print("Nothing to do")
        return

    # check Docker container is running
    # if restart: stop container container

    # run container container

    # check container container

    # send notification

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
