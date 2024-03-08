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
        parser.add_argument("-dv", "--volume", dest="dockervolume",
                            help="Docker volume to restore backup")
        parser.add_argument("-tp", "--targetpath", dest="targetpath",
                            help="Target file path to restore backup")
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

            if not (args.backupfile and args.targetpath and args.dockervolume):
                raise ValueError(
                    "Parameter --backupfile, --targetpath and --volume are mandatory in combination with --restore")

        if not args.restore and (args.dockervolume or args.targetpath or args.backupfile):
            raise ValueError(
                "Parameters --backupfile, --targetpath or --volume only available in combination with --restore")
