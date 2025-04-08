import json
import logging

from apt.config import Config, configure_logger, configure_sentry

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

CONFIG = Config()


def lambda_handler(event: dict, _context: dict) -> str:
    """AWS Lambda entrypoint."""
    CONFIG.check_required_env_vars()
    configure_sentry()
    configure_logger(logging.getLogger(), verbose=event.get("verbose", False))
    logger.debug(json.dumps(event))

    return "You have successfully called this lambda!"
