import logging

from util import cfg

logger = logging.getLogger(__name__)


def bar():
    print(f"config.X = {__name__}, {cfg.hasWarnings}")
