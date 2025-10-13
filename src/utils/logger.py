import logging
from ..config import settings


def setup_logger() -> logging.Logger:
    logger = logging.getLogger('org_bot')
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    ch = logging.StreamHandler()
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger
