import logging
import time

from dotenv import load_dotenv

from container.backup import Backup
from container.container import Container
from notification.dispatcher import Dispatcher
from util import cfg
from util.accessor import BackupDir, LocalHost, EnvSettings
from util.argparser import ArgParser
from util.logger import Logger

logger = logging.getLogger(__name__)


def create_backup(path, restart):
    logger.info(f"Start volume backup for container '{container.name}'")
    logger.debug(f"Container: {container.name}, Backup path: {path}")
    cfg.job_start_time = int(time.time())

    try:
        # check Docker daemon is running!
        if not LocalHost.is_docker_daemon_running():
            raise ValueError("Docker daemon not running as expected!")

        # check container exists
        if not container.exists():
            raise ValueError(f"Container '{container.name}' not found on '{LocalHost.get_hostname()}'")

        # get directory for volume container
        backup_dir = BackupDir(path)

        # create container directory
        backup_dir.create()

        # determine Docker volume of container
        if not container.is_volume_available():
            raise ValueError(f"No volumes to backup in container '{container.name}'")

        if restart:
            container.stop()

        # init Backup object and run backup tasks
        backup = Backup(container=container, backup_dir=backup_dir)
        backup.run_backup()

        should_change_ownership, should_change_permissions = backup.should_change_filesettings()

        if should_change_ownership:
            backup.change_file_ownership()

        if should_change_permissions:
            backup.change_file_permissions()

        # restart stopped container
        if restart:
            container.start()
            # Todo: check container

    except Exception as err:
        cfg.hasError = True
        cfg.errorMsg = err

        logger.exception(err)

    else:
        logger.info(f"Volume backup for container '{args.container}' completed successfully")

    finally:
        cfg.job_end_time = int(time.time())

        # send notification
        dispatcher = Dispatcher(container.name)
        dispatcher.notify_chat_receiver()
        dispatcher.notify_mqtt_receiver()

        logger.info(f"Volume backup done.")


if __name__ == "__main__":
    # load .env
    load_dotenv()
    EnvSettings().validate()

    args = ArgParser.parse_cli_args()

    # initialize objects
    Logger.init_logger(args.loglevel, args.container)
    container = Container(args.container)

    logger.debug(f"Start volume backup with args '{args}'")

    create_backup(args.path, args.restart)
