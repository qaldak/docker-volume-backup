import argparse
import logging
import os.path
import sys
import time

from dotenv import load_dotenv

from docker_volume_backup.container.backup import Backup
from docker_volume_backup.container.container import Container
from docker_volume_backup.container.recovery import Recovery
from docker_volume_backup.container.volume import Volume
from docker_volume_backup.notification.dispatcher import Dispatcher
from docker_volume_backup.util import cfg
from docker_volume_backup.util.accessor import BackupDir, LocalHost, EnvSettings
from docker_volume_backup.util.argparser import ArgParser
from docker_volume_backup.util.logger import Logger

logger = logging.getLogger(__name__)


def _restart_container(container):
    """
    Start a container that was stopped for the backup. A failing start is flagged as error and
    added to an already existing backup error instead of replacing it.
    """
    previous_error = cfg.errorMsg if cfg.hasError else None

    try:
        container.start()

    except Exception as err:
        logger.exception(err)

        cfg.hasError = True
        if previous_error:
            cfg.errorMsg = f"{previous_error}. Additionally, container '{container.name}' could not be restarted: {err}"
        else:
            cfg.errorMsg = err


def _send_notifications(container_name: str):
    """
    Send the configured notifications. A failing notification is logged. It must neither stop the other
    notification nor change the result of the backup (see #156: an exception of one notification used to leave
    the finally block of create_backup, so the next notification was skipped and the process ended with a traceback).
    """
    try:
        dispatcher = Dispatcher(container_name)

        # The two methods are only collected here, they are NOT called yet (no parentheses): nothing is sent
        # at this point. Both return None, the return value is not used.
        notifications = (dispatcher.notify_chat_receiver, dispatcher.notify_mqtt_receiver)

    except Exception as err:
        logger.exception(f"Notifications could not be prepared: {err}")
        return

    # "notify" is the loop variable: it is bound to one of the two methods per pass, notify() sends that message.
    # Same as calling dispatcher.notify_chat_receiver() and dispatcher.notify_mqtt_receiver() one after the other,
    # but each call has its own try/except, so a failing chat notification can not skip the MQTT notification.
    for notify in notifications:
        try:
            notify()

        except Exception as err:
            logger.exception(f"Notification failed ({getattr(notify, '__name__', 'unknown')}): {err}")


def create_backup(container, path, restart) -> bool:
    """
    Run the volume backup of a container and send the configured notifications.

    :return: True if the backup (including the container restart) completed without error
    """
    logger.info(f"Start volume backup for container '{container.name}'")
    logger.debug(f"Container: {container.name}, Backup path: {path}")
    cfg.job_start_time = int(time.time())
    container_stopped = False

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
            # set before stop(): a failing stop() may leave the container (or parts of it) stopped
            container_stopped = True
            container.stop()

        # init Backup object and run backup tasks
        backup = Backup(container=container, backup_dir=backup_dir)
        backup.run_backup()

        should_change_ownership, should_change_permissions = backup.should_change_filesettings()

        if should_change_ownership:
            backup.change_file_ownership()

        if should_change_permissions:
            backup.change_file_permissions()

    except Exception as err:
        cfg.hasError = True
        cfg.errorMsg = err

        logger.exception(err)

    finally:
        # always restart a container stopped for the backup, also if the backup failed
        if container_stopped:
            _restart_container(container)

        cfg.job_end_time = int(time.time())

        # determine the result before notifying: a failing notification must not change the backup result
        success = not cfg.hasError
        if success:
            logger.info(f"Volume backup for container '{container.name}' completed successfully")

        _send_notifications(container.name)

        logger.info(f"Volume backup done.")

    return success


def _confirm_overwrite(docker_volume: str, assume_yes: bool) -> bool:
    """
    Ask before files in an existing Docker volume are overwritten. Without a terminal (cron, scripts) nobody can
    answer: the restore continues as it always did, with a warning.

    :return: True if the restore should continue
    """
    warning = f"Docker volume '{docker_volume}' already contains files. Files with the same name are overwritten."

    if assume_yes or not sys.stdin.isatty():
        logger.warning(warning)
        print(f"Warning: {warning}")
        return True

    return input(f"{warning} Continue? (y/N): ").strip().lower() in ("y", "yes")


def restore_backup(docker_volume, target_path, backup_file, source_path=None, assume_yes=False) -> bool:
    """
    :return: True if the Docker volume was restored completely, False if the restore was not run or is incomplete
    """
    print(f"Launching recovery process ...")
    logger.info(f"Launching recovery process. Docker volume: {docker_volume}, target path: {target_path}, "
                f"backup file to restore: {backup_file}, source path: {source_path}")

    if not os.path.exists(backup_file):
        raise FileNotFoundError(f"Backup file not found: '{backup_file}'")

    recovery = Recovery(docker_volume=docker_volume, target_path=target_path, backup_file=backup_file,
                        source_path=source_path)

    # check which part of the backup file is restored, before a Docker volume is touched or created
    recovery.resolve_source_path()

    volume = Volume(docker_volume)
    if volume.exists():
        running = volume.containers(running_only=True)
        if running:
            error_msg = (f"Docker volume '{docker_volume}' is used by running container(s): {', '.join(running)}. "
                         f"Stop the container(s) before restoring. Nothing was restored.")
            logger.error(error_msg)
            print(f"Error: {error_msg}", file=sys.stderr)
            return False

        stopped = volume.containers()
        if stopped:
            warning = f"Docker volume '{docker_volume}' is used by stopped container(s): {', '.join(stopped)}."
            logger.warning(warning)
            print(f"Warning: {warning}")

        if recovery.volume_has_content() and not _confirm_overwrite(docker_volume, assume_yes):
            print("Restore canceled. Nothing was restored.")
            logger.info("Restore canceled by user.")
            return False

    else:
        new_volume = volume.create()
        logger.info(f"New Docker volume created: {new_volume}")

    recovery.restore_volume_backup()

    restored_completely = recovery.check_recovery()

    print("Recovery process done.")

    return restored_completely


def init_environment() -> argparse.Namespace:
    """
    Administrative part of the start: load and validate the .env settings, parse the command line
    and initialize logging. Kept out of main() so that main() only runs the actual backup/restore.

    :return: parsed command line arguments
    """
    load_dotenv()
    EnvSettings().validate()

    args = ArgParser.parse_cli_args()

    log_identifier = args.container if args.backup else "restore-" + args.dockervolume
    Logger.init_logger(args.loglevel, log_identifier)

    return args


def main(args: argparse.Namespace) -> int:
    """
    Run backup or restore according to the command line arguments.

    :return: process exit code: 0 on success, 1 if the backup failed or the restored volume is incomplete
    """
    logger.debug(f"Start volume backup with args '{args}'")

    if args.restore:
        return 0 if restore_backup(args.dockervolume, args.targetpath, args.backupfile, args.sourcepath, args.yes) else 1

    return 0 if create_backup(Container(args.container), args.path, args.restart) else 1


if __name__ == "__main__":
    sys.exit(main(init_environment()))
