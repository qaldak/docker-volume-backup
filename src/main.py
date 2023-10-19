import logging

from container.backup import Volume
from container.container import Container
from notification.dispatcher import Dispatcher, Receiver
from util import cfg
from util.accessor import BackupDir, LocalHost
from util.argparser import ArgParser
from util.logger import Logger

logger = logging.getLogger(__name__)


def main(path, restart):
    logger.info(f"Start volume backup for container '{container.name}'")
    logger.debug(f"Container: {container.name}, Backup path: {path}")

    # Todo: concept: where notification should be triggered, centralised vs decentralised

    try:
        # check Docker daemon is running!
        if not LocalHost.is_docker_daemon_running():
            raise ValueError("Docker daemon not running as expected!")

        # check container exists
        if not container.exists():
            logger.debug(f"Container '{container.name}' not found on '{LocalHost.get_hostname()}'")
            # Todo: raise Exception

        # get directory for volume container
        backup_dir = BackupDir(path, container.name)

        # create container directory
        backup_dir.create()

        # determine Docker volume of container
        if not container.is_volume_available():
            logger.debug(f"No volumes to backup in container '{container.name}'")
            Dispatcher(Receiver.SLACK, "Error", "Mqtt-msg").notify_receiver()
            # raise AssertionError("No volumes to backup")
            # return
            # Todo: raise Exception

        if restart:
            container.stop()

        Volume.run_backup(container, backup_dir)

        if restart:
            container.start()
            # Todo: check container

        # send notification

        # Todo: check try / finally
    finally:
        if cfg.hasError:
            print("Foo")

    logger.info(f"Volume backup for container '{args.container}' completed successfully")


if __name__ == "__main__":
    args = ArgParser.parse_cli_args()

    # initialize objects
    Logger.init_logger(args.loglevel)
    container = Container(args.container)

    logger.debug(f"Start volume backup with args '{args}'")

    main(args.path, args.restart)
