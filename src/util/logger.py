import logging
import os


class Logger:

    @staticmethod
    def init_logger(loglevel, container: str):
        logdir = os.getenv("LOG_DIR")

        if not os.path.isdir(logdir):
            os.makedirs(logdir)

        # Todo: funcName vs name
        logging.basicConfig(level=loglevel, filename=f"{logdir}/{container.replace('_', '-')}-volume-backup.log",
                            format='%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')
