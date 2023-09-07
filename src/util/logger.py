import logging
import os


class Logger:

    @staticmethod
    def init_logger(loglevel):
        logdir = "log"
        if not os.path.isdir(logdir):
            os.makedirs(logdir)

        # Todo: funcName vs name
        logging.basicConfig(level=loglevel, filename=f"{logdir}/docker-volume-backup.log",
                            format='%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')
