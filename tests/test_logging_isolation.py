"""The package must log its own records without configuring the host."""

import io
import logging
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

import resistant_kafka_avataa.consumer as consumer_module
import resistant_kafka_avataa.logger as logger_module
from resistant_kafka_avataa.logger import PACKAGE_LOGGER_NAME, configure_logger
from resistant_kafka_avataa.producer import ProducerInitializer


CONSUMER_LOGGER = "resistant_kafka_avataa.consumer"
MESSAGE_KEY = b"MO:created"
MESSAGE_VALUE = b"secret-token-value"

_process_kafka_error_message = getattr(
    consumer_module, "__process_kafka_error_message"
)


def package_fallback_handlers() -> list[logging.Handler]:
    """Collect the fallback handlers the package installed on itself."""
    return [
        handler
        for handler in logging.getLogger(PACKAGE_LOGGER_NAME).handlers
        if isinstance(handler, logger_module._FallbackHandler)
    ]


def make_message() -> MagicMock:
    """Build a Kafka message mock carrying a key and a secret value."""
    message = MagicMock()
    message.key.return_value = MESSAGE_KEY
    message.value.return_value = MESSAGE_VALUE
    message.topic.return_value = "documents.changes"
    message.partition.return_value = 0
    message.offset.return_value = 114
    return message


def test_logger_name_is_placed_under_the_package_namespace() -> None:
    """A name from outside the package namespace is moved under it."""
    # Arrange / Act
    logger = configure_logger("kafka_processor")

    # Assert
    assert logger.name == f"{PACKAGE_LOGGER_NAME}.kafka_processor"


def test_module_logger_keeps_its_dotted_name() -> None:
    """A __name__ already inside the namespace is used unchanged."""
    # Arrange / Act
    logger = configure_logger(CONSUMER_LOGGER)

    # Assert
    assert logger.name == CONSUMER_LOGGER


def test_configure_logger_installs_exactly_one_fallback_handler() -> None:
    """Repeated calls configure the package logger once, not once per call."""
    # Arrange / Act
    configure_logger(CONSUMER_LOGGER)
    configure_logger("kafka_processor")
    configure_logger()

    # Assert
    assert len(package_fallback_handlers()) == 1


def test_configure_logger_does_not_override_a_level_set_by_the_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A level chosen by the host survives every later configure_logger call."""
    # Arrange
    package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    monkeypatch.setattr(package_logger, "level", logging.CRITICAL)
    monkeypatch.setenv("RESISTANT_KAFKA_LOG_LEVEL", "DEBUG")

    # Act
    configure_logger(CONSUMER_LOGGER)

    # Assert
    assert package_logger.level == logging.CRITICAL


def test_fallback_handler_writes_when_no_other_handler_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With nothing configured, the package still shows its own records."""
    # Arrange — the handler under test is the one configure_logger installed
    logger = configure_logger(CONSUMER_LOGGER)
    handler = package_fallback_handlers()[0]
    stream = io.StringIO()
    monkeypatch.setattr(handler, "stream", stream)
    monkeypatch.setattr(logging.getLogger(), "handlers", [])

    # Act
    logger.warning("topic is missing")

    # Assert
    assert "topic is missing" in stream.getvalue()


def test_fallback_handler_stays_silent_when_host_configured_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host handler means the package must not print a second copy."""
    # Arrange
    logger = configure_logger(CONSUMER_LOGGER)
    handler = package_fallback_handlers()[0]
    package_stream = io.StringIO()
    monkeypatch.setattr(handler, "stream", package_stream)
    host_stream = io.StringIO()
    monkeypatch.setattr(
        logging.getLogger(), "handlers", [logging.StreamHandler(host_stream)]
    )

    # Act
    logger.warning("topic is missing")

    # Assert
    assert package_stream.getvalue() == ""
    assert "topic is missing" in host_stream.getvalue()


def test_processing_error_logs_no_message_key_or_value_at_any_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Neither the key nor the payload reaches the log, DEBUG included."""
    # Arrange
    consumer = MagicMock()
    consumer._config.processor_name = "DocumentsChangesProcessor"
    consumer._config.topic_to_subscribe = "documents.changes"

    # Act
    with caplog.at_level(logging.DEBUG, logger=PACKAGE_LOGGER_NAME):
        _process_kafka_error_message(
            self=consumer,
            error_instance=ValueError("boom"),
            raise_error=False,
            store_error_messages=False,
            redis_client=None,
            message=make_message(),
        )

    # Assert
    assert "boom" in caplog.text
    assert "114" in caplog.text
    assert MESSAGE_VALUE.decode() not in caplog.text
    assert MESSAGE_KEY.decode() not in caplog.text


def test_delivery_report_logs_no_record_key_at_any_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The producer reports coordinates, never the record key."""
    # Arrange
    message = make_message()

    # Act
    with caplog.at_level(logging.DEBUG, logger=PACKAGE_LOGGER_NAME):
        ProducerInitializer._delivery_report(None, message)
        ProducerInitializer._delivery_report("broker rejected it", message)

    # Assert
    assert "documents.changes" in caplog.text
    assert "broker rejected it" in caplog.text
    assert MESSAGE_KEY.decode() not in caplog.text


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Phase 2: logging.basicConfig in consumer.py is deliberately kept for "
        "one release while the consuming services add their own logging "
        "setup. Remove this marker together with that call."
    ),
)
def test_import_does_not_touch_root_logger() -> None:
    """Importing the package changes neither handlers nor level of root."""
    # Arrange — a separate process: here the package is already imported
    code = (
        "import logging;"
        "root=logging.getLogger();"
        "before=(len(root.handlers), root.level);"
        "import resistant_kafka_avataa;"
        "after=(len(root.handlers), root.level);"
        "print(before==after)"
    )

    # Act
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )

    # Assert
    assert result.stdout.strip() == "True", result.stdout or result.stderr
