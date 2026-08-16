import logging
import os

PACKAGE_LOGGER_NAME = "resistant_kafka_avataa"

_LOG_LEVEL_ENV_VAR = "RESISTANT_KAFKA_LOG_LEVEL"
_DEFAULT_LOG_LEVEL = "INFO"
_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"


class _FallbackHandler(logging.StreamHandler):
    """
    Prints package records only while nothing else would print them.

    A library must not decide where the host service writes its logs, but a
    service that never configured logging would otherwise lose everything
    below WARNING. This handler resolves both: it stays silent as soon as any
    handler outside this package can receive the record, and writes to stderr
    only when there is none. The check happens on every record rather than
    once at import time, because a service usually configures its logging
    after importing the modules that use it.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Writes the record only when no external handler will receive it.

        :param record: The record about to be emitted.
        """
        if _has_external_handler(record.name):
            return

        super().emit(record)


def _has_external_handler(logger_name: str) -> bool:
    """
    Tells whether a handler outside this package can receive the record.

    Walks the logger chain the same way ``logging`` does when dispatching a
    record, stopping where propagation stops.

    :param logger_name: Name of the logger that produced the record.

    :returns: True if some handler other than the package fallback is reached.
    """
    logger = logging.getLogger(logger_name)

    while logger is not None:
        for handler in logger.handlers:
            if not isinstance(handler, _FallbackHandler):
                return True

        if not logger.propagate:
            return False

        logger = logger.parent

    return False


def _configure_package_logger() -> logging.Logger:
    """
    Sets the level and the fallback handler on the package logger, once.

    Only the ``resistant_kafka_avataa`` logger is touched: the root logger and
    the host service's own loggers are left exactly as they are. The level is
    taken from the environment only while the logger has none of its own, so
    a host that sets the level keeps it — this function is called on every
    ``configure_logger`` and must never overwrite that choice.

    :returns: The package logger.
    """
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)

    if logger.level == logging.NOTSET:
        log_level = os.getenv(_LOG_LEVEL_ENV_VAR, _DEFAULT_LOG_LEVEL).upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

    if any(
        isinstance(handler, _FallbackHandler) for handler in logger.handlers
    ):
        return logger

    handler = _FallbackHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(handler)

    return logger


def configure_logger(name: str = PACKAGE_LOGGER_NAME) -> logging.Logger:
    """
    Returns a logger inside the package namespace.

    :param name: Logger name, normally the module's ``__name__``. Names
                 outside the package namespace are placed under it, so a host
                 service can configure everything this package logs through
                 the single ``resistant_kafka_avataa`` prefix.

    :returns: The logger to write to.
    """
    _configure_package_logger()

    if name != PACKAGE_LOGGER_NAME and not name.startswith(
        f"{PACKAGE_LOGGER_NAME}."
    ):
        name = f"{PACKAGE_LOGGER_NAME}.{name}"

    return logging.getLogger(name)
