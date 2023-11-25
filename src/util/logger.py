import logging
import os
from logging.handlers import RotatingFileHandler


class Logger:

    @staticmethod
    def init_logger(loglevel, container: str):
        logdir = os.getenv("LOG_DIR")
        logfile = f"{container}-volume-backup.log"

        loghandler = RotatingFileHandler(f"{logdir}/{logfile}", maxBytes=1049000, backupCount=1)
        loghandler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s'))

        if not os.path.isdir(logdir):
            os.makedirs(logdir)

        logging.basicConfig(level=loglevel, handlers=[loghandler])
