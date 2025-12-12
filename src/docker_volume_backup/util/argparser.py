import argparse
import logging


class ArgParser:

    @staticmethod
    def parse_cli_args():
        parser = argparse.ArgumentParser()
        parser.add_argument("--backup", action="store_true", dest="backup",
                            help="Backup Docker volume. Defaults from .env file, optional parameter --path and "
                                 "--restart")
        parser.add_argument("--restore", action="store_true", dest="restore",
                            help="Restore backup to Docker volume. Needs parameter --backupfile, --volume and "
                                 "--targetpath")

        if parser.parse_known_args()[0].backup:
            parser.add_argument("container", help="Define Docker container whose volume should be backed up")
            parser.add_argument("-p", "--path",
                                help="Backup destination path (Default by ENV settings)")
            parser.add_argument("-r", "--restart", action="store_true", dest="restart",
                                help="Stops Docker container for backup and restart when done")

        if parser.parse_known_args()[0].restore:
            parser.add_argument("--backupfile", dest="backupfile",
                                help="Path and name of backup file to restore")
            parser.add_argument("-dv", "--volume", dest="dockervolume",
                                help="Docker volume to restore backup")
            parser.add_argument("-tp", "--targetpath", dest="targetpath",
                                help="Target path on Docker volume to restore backup")

        parser.add_argument("--debug", action="store_const", dest="loglevel", const=logging.DEBUG,
                            default=logging.INFO,
                            help="Enable debug mode")

        args = parser.parse_args()
        ArgParser.__validate_args(args)

        return args

    @staticmethod
    def __validate_args(args):
        if args.backup and args.restore:
            raise ValueError("Combination of --backup and --restore is not allowed.")

        if args.restore:
            if not (args.backupfile and args.targetpath and args.dockervolume):
                raise ValueError(
                    "Parameter --backupfile, --targetpath and --volume are mandatory in combination with --restore")

            if not args.targetpath.startswith("/"):
                raise ValueError(f"Parameter --targetpath has to start with '/' but given '{args.targetpath}'")
