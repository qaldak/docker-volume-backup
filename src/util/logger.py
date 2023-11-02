import logging
import os


class Logger:

    @staticmethod
    def init_logger(loglevel, container):
        logdir = "log"
        if not os.path.isdir(logdir):
            os.makedirs(logdir)

        # Todo: funcName vs name
        logging.basicConfig(level=loglevel, filename=f"{logdir}/{container}-volume-backup.log",
                            format='%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')
