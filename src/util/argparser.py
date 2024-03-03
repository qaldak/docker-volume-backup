import argparse
import logging


class ArgParser:

    @staticmethod
    def parse_cli_args():
        parser = argparse.ArgumentParser()
        parser.add_argument("container", help="Define Docker container whose volume should be backed up")
        parser.add_argument("-p", "--path",
                            help="Backup destination path (Default by ENV settings)")
        parser.add_argument("-r", "--restart", action="store_true", dest="restart",
                            help="Stops Docker container for backup and restart when done")
        parser.add_argument("--restore", action="store_true", dest="restore",
                            help="Restore backup to Docker volume. Needs parameter --backupfile and --volume")
        parser.add_argument("--backupfile", help="Path and name of backup file to restore")
        parser.add_argument("--volume", dest="targetvolume",
                            help="Target volume to restore backup")
        parser.add_argument("--debug", action="store_const", dest="loglevel", const=logging.DEBUG,
                            default=logging.INFO,
                            help="Set loglevel to DEBUG")

        args = parser.parse_args()
        ArgParser.__validate_args(args)

        return args

    @staticmethod
    def __validate_args(args):
        if args.restore:
            if args.path or args.restart:
                raise ValueError("Parameter --path and --restart not available in combination with --restore")

            if not (args.backupfile and args.targetvolume):
                raise ValueError("Parameter --backupfile and --volume are mandatory in combination with --restore")

        if not args.restore and (args.targetvolume or args.backupfile):
            raise ValueError("Parameters --backupfile and --volume only available in combination with --restore")
