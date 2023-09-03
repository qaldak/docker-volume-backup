import logging

from helper import cfg

logger = logging.getLogger(__name__)


def bar():
    print(f"config.X = {__name__}, {cfg.hasWarnings}")
    logger.info("Foo")
    cfg.hasWarnings = False
