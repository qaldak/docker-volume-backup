import argparse
import logging


class ArgParser:
    @staticmethod
    def parse_cli_args():
        parser = argparse.ArgumentParser()
        parser.add_argument("container", help="Define Docker container whose volume should be backed up")
        parser.add_argument("-p", "--path",
                            help="Backup destination path (Default by ENV settings)")  # Todo: Default Path from ENV file
        parser.add_argument("-r", "--restart", action="store_true", dest="restart",
                            help="Stops Docker container for docker and restart when done")
        parser.add_argument("--debug", action="store_const", dest="loglevel", const=logging.DEBUG,
                            default=logging.DEBUG,
                            help="Set loglevel to DEBUG")
        return parser.parse_args()
