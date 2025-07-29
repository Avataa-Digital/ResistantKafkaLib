import logging
import os


def configure_logger(name: str = "resistant_kafka_avataa_logger"):
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = os.getenv("RESISTANT_KAFKA_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    logger.setLevel(level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
