"""Startup tests: a consumer that cannot start must say so in the log."""

import asyncio
import logging
from unittest.mock import MagicMock

import pytest
from confluent_kafka import KafkaException

import resistant_kafka_avataa.consumer as consumer_module
from resistant_kafka_avataa.common_exceptions import KafkaConnectionError
from resistant_kafka_avataa.consumer import ConsumerInitializer
from resistant_kafka_avataa.consumer_schemas import ConsumerConfig


LOGGER_NAME = "resistant_kafka_avataa.consumer"
TOPIC = "documents.changes"
PROCESSOR = "DocumentsChangesProcessor"
BROKER = "localhost:9092"
#: Discard port: refuses connections, so a real client reaches no broker.
UNREACHABLE_BROKER = "localhost:9"


class _StopLoop(Exception):
    """Breaks the endless polling loop of process_kafka_connection."""


class _NeverEndingConsumer:
    """Stand-in whose process() runs until it is cancelled."""

    def __init__(self, name: str, events: list[str] | None = None):
        self._config = MagicMock()
        self._config.processor_name = name
        self._consumer = MagicMock()
        self.name = name
        self.events = events if events is not None else []
        self._consumer.close.side_effect = lambda: self.events.append(
            f"closed:{name}"
        )
        self.running = asyncio.Event()
        self.cancelled = False

    async def start(self) -> None:
        return None

    async def process(self) -> None:
        self.running.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.cancelled = True
            self.events.append(f"cancelled:{self.name}")
            raise


class _SlowStartConsumer:
    """Stand-in that never finishes starting, to be cancelled mid-startup."""

    def __init__(self, name: str):
        self._config = MagicMock()
        self._config.processor_name = name
        self._consumer = MagicMock()
        self.starting = asyncio.Event()

    async def start(self) -> None:
        self.starting.set()
        await asyncio.sleep(3600)

    async def process(self) -> None:
        raise AssertionError("a consumer that never started must not process")


class _FakeConsumer:
    """Minimal stand-in for ConsumerInitializer used by the loop tests."""

    def __init__(self, name: str, start_error: Exception | None = None):
        self._config = MagicMock()
        self._config.processor_name = name
        self._consumer = MagicMock()
        self._start_error = start_error
        self.processed = 0

    async def start(self) -> None:
        if self._start_error is not None:
            raise self._start_error

    async def process(self) -> None:
        self.processed += 1
        raise _StopLoop()


def make_config() -> ConsumerConfig:
    """Build a consumer configuration pointing at a topic under test."""
    return ConsumerConfig(
        topic_to_subscribe=TOPIC,
        processor_name=PROCESSOR,
        bootstrap_servers=BROKER,
        group_id="test-group",
    )


def make_metadata(*topics: str) -> MagicMock:
    """Build cluster metadata listing the given topic names."""
    metadata = MagicMock()
    metadata.topics = {topic: MagicMock() for topic in topics}
    return metadata


@pytest.fixture
def kafka_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch the confluent Consumer, return the client mock it hands out."""
    client = MagicMock()
    monkeypatch.setattr(
        consumer_module, "Consumer", MagicMock(return_value=client)
    )
    return client


def test_missing_topic_does_not_raise_and_subscribes(
    kafka_client: MagicMock,
) -> None:
    """A missing topic does not stop the consumer: it subscribes anyway."""
    # Arrange
    kafka_client.list_topics.return_value = make_metadata("some.other.topic")
    initializer = ConsumerInitializer(config=make_config())

    # Act
    asyncio.run(initializer.start())

    # Assert
    initializer._consumer.subscribe.assert_called_once()


def test_missing_topic_logs_warning_naming_processor_topic_broker(
    kafka_client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """The missing-topic warning names the processor, the topic and the broker."""
    # Arrange
    kafka_client.list_topics.return_value = make_metadata("some.other.topic")
    initializer = ConsumerInitializer(config=make_config())

    # Act
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        asyncio.run(initializer.start())

    # Assert
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert PROCESSOR in message
    assert TOPIC in message
    assert BROKER in message


def test_metadata_fetch_failure_does_not_raise(
    kafka_client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """An unreachable broker is a warning, not a startup failure."""
    # Arrange
    kafka_client.list_topics.side_effect = KafkaException("broker is down")
    initializer = ConsumerInitializer(config=make_config())

    # Act
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        asyncio.run(initializer.start())

    # Assert
    assert "could not check" in caplog.text
    initializer._consumer.subscribe.assert_called_once()


def test_existing_topic_logs_no_warning(
    kafka_client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """The happy path stays silent at WARNING level."""
    # Arrange
    kafka_client.list_topics.return_value = make_metadata(TOPIC)
    initializer = ConsumerInitializer(config=make_config())

    # Act
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        asyncio.run(initializer.start())

    # Assert
    assert caplog.records == []
    initializer._consumer.subscribe.assert_called_once()


def test_rejected_configuration_raises_kafka_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configuration Kafka refuses leaves the package as our own exception."""
    # Arrange
    monkeypatch.setattr(
        consumer_module,
        "Consumer",
        MagicMock(side_effect=KafkaException("unknown property")),
    )

    # Act
    with pytest.raises(KafkaConnectionError) as raised:
        ConsumerInitializer(config=make_config())

    # Assert — our type, our processor named, their exception kept as the cause
    assert PROCESSOR in str(raised.value)
    assert isinstance(raised.value.__cause__, KafkaException)


def test_topic_check_uses_the_consumer_and_builds_no_second_client(
    kafka_client: MagicMock,
) -> None:
    """The topic list is read through the consumer's own client, not an admin one."""
    # Arrange
    kafka_client.list_topics.return_value = make_metadata(TOPIC)
    initializer = ConsumerInitializer(config=make_config())

    # Act
    asyncio.run(initializer.start())

    # Assert — an admin client would be handed the consumer-only settings
    kafka_client.list_topics.assert_called_once()
    assert not hasattr(consumer_module, "AdminClient")


def test_the_client_queue_is_served_before_metadata_is_requested(
    kafka_client: MagicMock,
) -> None:
    """poll() runs before list_topics, or SASL/OAUTHBEARER never gets a token.

    Both calls happen in any version of this code, so asserting that they were
    made proves nothing. Only their order does.
    """
    # Arrange
    kafka_client.list_topics.return_value = make_metadata(TOPIC)
    initializer = ConsumerInitializer(config=make_config())

    # Act
    asyncio.run(initializer.start())

    # Assert
    called = [name for name, _, _ in kafka_client.mock_calls]
    assert called.index("poll") < called.index("list_topics")


def test_starting_a_consumer_emits_no_librdkafka_config_warnings(
    capfd: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real librdkafka accepts every setting the startup path gives it.

    No broker is needed and none is used: librdkafka parses the configuration
    while the client is being created and prints its warnings there, long
    before it connects. Mocks cannot cover this — they never see the settings
    librdkafka itself objects to.
    """
    # Arrange — a port nothing listens on, so no broker is touched even where
    # one happens to run locally, and a short timeout to pay for it once
    monkeypatch.setattr(consumer_module, "_TOPIC_METADATA_TIMEOUT_SECONDS", 0.5)
    config = make_config()
    config.bootstrap_servers = UNREACHABLE_BROKER
    initializer = ConsumerInitializer(config=config)

    # Act
    try:
        asyncio.run(initializer.start())
    finally:
        initializer._consumer.close()

    # Assert
    assert "CONFWARN" not in capfd.readouterr().err


def test_process_kafka_connection_logs_before_reraising(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An exception leaving the coroutine is logged, so the task is not silent."""
    # Arrange
    failing = _FakeConsumer(
        "Failing", start_error=KafkaConnectionError("broker unreachable")
    )

    # Act
    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        with pytest.raises(KafkaConnectionError):
            asyncio.run(consumer_module.process_kafka_connection([failing]))

    # Assert
    assert "Kafka consumer connection stopped" in caplog.text


def test_one_failing_start_does_not_block_other_consumers() -> None:
    """A consumer that cannot start is dropped; the remaining ones still run."""
    # Arrange
    failing = _FakeConsumer(
        "Failing", start_error=KafkaConnectionError("broker unreachable")
    )
    working = _FakeConsumer("Working")

    # Act
    with pytest.raises(_StopLoop):
        asyncio.run(
            consumer_module.process_kafka_connection([failing, working])
        )

    # Assert
    assert working.processed == 1
    assert failing.processed == 0


def test_consumer_that_failed_to_start_is_closed() -> None:
    """A dropped consumer releases its client instead of leaking threads."""
    # Arrange
    failing = _FakeConsumer(
        "Failing", start_error=KafkaConnectionError("broker unreachable")
    )
    working = _FakeConsumer("Working")

    # Act
    with pytest.raises(_StopLoop):
        asyncio.run(
            consumer_module.process_kafka_connection([failing, working])
        )

    # Assert — closed although it never reached processing
    failing._consumer.close.assert_called_once()
    assert failing.processed == 0


def test_started_consumers_are_closed_when_a_processor_fails() -> None:
    """A processor error tears the whole connection down, clients included."""
    # Arrange
    first = _FakeConsumer("First")
    second = _FakeConsumer("Second")

    # Act
    with pytest.raises(_StopLoop):
        asyncio.run(consumer_module.process_kafka_connection([first, second]))

    # Assert
    first._consumer.close.assert_called_once()
    second._consumer.close.assert_called_once()


def test_remaining_processors_are_cancelled_before_their_client_is_closed() -> (
    None
):
    """Cancellation must come from the teardown, not from the loop shutdown.

    Asserting only that the task ends up cancelled passes even when nothing
    cancels it: asyncio.run() cancels whatever is left when it closes the
    loop. Only the order proves who did it.
    """
    # Arrange
    events: list[str] = []
    failing = _FakeConsumer("Failing")
    endless = _NeverEndingConsumer("Endless", events=events)

    # Act
    with pytest.raises(_StopLoop):
        asyncio.run(
            consumer_module.process_kafka_connection([failing, endless])
        )

    # Assert
    assert endless.cancelled is True
    assert events.index("cancelled:Endless") < events.index("closed:Endless")


def test_consumers_are_closed_when_the_connection_is_cancelled() -> None:
    """Shutdown cancellation releases the clients instead of leaking them."""
    # Arrange
    endless = _NeverEndingConsumer("Endless")

    async def scenario() -> None:
        task = asyncio.create_task(
            consumer_module.process_kafka_connection([endless])
        )
        await endless.running.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    # Act
    asyncio.run(scenario())

    # Assert
    assert endless.cancelled is True
    endless._consumer.close.assert_called_once()


def test_failed_consumer_is_closed_while_the_connection_keeps_running() -> None:
    """A dropped consumer must not hold its client for the whole process.

    Asserting after the connection ends proves nothing: everything is closed
    then. The healthy consumer may run for months, so the check has to happen
    while it is still polling.
    """
    # Arrange
    failing = _FakeConsumer(
        "Failing", start_error=KafkaConnectionError("broker unreachable")
    )
    endless = _NeverEndingConsumer("Endless")

    async def scenario() -> None:
        task = asyncio.create_task(
            consumer_module.process_kafka_connection([failing, endless])
        )
        await endless.running.wait()

        # The connection is alive and polling right now.
        failing._consumer.close.assert_called_once()
        endless._consumer.close.assert_not_called()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    # Act
    asyncio.run(scenario())

    # Assert — and it is still closed exactly once, not twice
    failing._consumer.close.assert_called_once()
    endless._consumer.close.assert_called_once()


def test_consumers_are_closed_when_cancelled_during_startup() -> None:
    """Cancellation while starting still releases the clients."""
    # Arrange
    slow = _SlowStartConsumer("Slow")

    async def scenario() -> None:
        task = asyncio.create_task(
            consumer_module.process_kafka_connection([slow])
        )
        await slow.starting.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    # Act
    asyncio.run(scenario())

    # Assert
    slow._consumer.close.assert_called_once()


def test_unexpected_start_error_is_not_turned_into_a_skipped_consumer() -> None:
    """Only Kafka startup errors are survivable; a bug must propagate."""
    # Arrange
    broken = _FakeConsumer("Broken", start_error=ValueError("bug in start"))
    working = _FakeConsumer("Working")

    # Act / Assert
    with pytest.raises(ValueError, match="bug in start"):
        asyncio.run(consumer_module.process_kafka_connection([broken, working]))

    assert working.processed == 0
    working._consumer.close.assert_called_once()
