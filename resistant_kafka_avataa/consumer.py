import asyncio
import datetime
import functools
import logging
import uuid
from abc import abstractmethod
from asyncio import Future
from typing import Any

from confluent_kafka import Consumer, KafkaException, cimpl
from confluent_kafka.admin import AdminClient

from resistant_kafka_avataa.common_exceptions import (
    ConfigurationError,
    KafkaMessageError,
    KafkaConnectionError,
)
from resistant_kafka_avataa.common_schemas import RedisMessage
from resistant_kafka_avataa.consumer_schemas import ConsumerConfig
from resistant_kafka_avataa.logger import configure_logger
from resistant_kafka_avataa.message_desirializers import MessageDeserializer

# A library must not configure the root logger, and this call is scheduled for
# removal. It is kept for one release only because the consuming services do
# not configure logging themselves yet: dropping it now would silence their own
# INFO records, not just ours. See "Logging" in README.md.
logging.basicConfig(level=logging.INFO)

_logger = configure_logger(__name__)

#: Seconds to wait for cluster metadata when checking that a topic exists.
_TOPIC_METADATA_TIMEOUT_SECONDS = 10.0

#: Startup errors that cost one consumer, not the whole connection.
_EXPECTED_START_ERRORS = (KafkaConnectionError, KafkaException)


class ConsumerInitializer:
    def __init__(
        self, config: ConsumerConfig, deserializers: MessageDeserializer = None
    ) -> None:
        """
        Initializes and manages a Kafka consumer based on the given configuration.

        :param config: The configuration for the consumer.
        :param deserializers: Deserializers objects for deserializing Kafka messages
                            (custom deserializers are supported, and default string too)
        """
        self._consumer = Consumer(self._set_consumer_config(config=config))
        self._topic_to_subscribe = config.topic_to_subscribe
        self._config = config
        self._deserializers = deserializers

    @staticmethod
    def _set_consumer_config(config: ConsumerConfig) -> dict:
        """
        Prepares the dictionary of Kafka consumer configuration based on the given settings.
        :param config: The consumer configuration.

        :returns: Dictionary of Kafka consumer configuration parameters.
        """
        consumer_config = {
            "bootstrap.servers": config.bootstrap_servers,
            "group.id": config.group_id,
            "auto.offset.reset": config.auto_offset_reset,
            "enable.auto.commit": config.enable_auto_commit,
        }

        if config.security_config:
            if config.security_config.oauth_cb:
                consumer_config["oauth_cb"] = config.security_config.oauth_cb
            consumer_config["security.protocol"] = (
                config.security_config.security_protocol
            )
            consumer_config["sasl.mechanisms"] = (
                config.security_config.sasl_mechanisms
            )
            consumer_config.update(config.security_config.to_confluent_extra())

        return consumer_config

    def _connection_flag_method(self, *args) -> None:
        """
        Logs a message when the consumer has successfully subscribed to the topic.
        """
        _logger.info(
            "%s successfully subscribed to the topic %s",
            self._config.processor_name,
            self._config.topic_to_subscribe,
        )

    async def _check_topic_is_available(self) -> None:
        """
        Reports a missing topic as a warning without stopping the consumer.

        Neither a missing topic nor an unreachable broker is treated as a
        startup failure: the topic may be created later, and the subscription
        below picks it up as soon as it appears. Only a configuration that
        cannot produce an admin client at all is fatal.

        :raises KafkaConnectionError: if the admin client cannot be built
                                      from the consumer configuration.
        """
        try:
            admin_client = AdminClient(
                self._set_consumer_config(config=self._config)
            )
        except KafkaException as ex:
            raise KafkaConnectionError(
                f"{self._config.processor_name}: cannot check topic "
                f"'{self._topic_to_subscribe}', the consumer configuration "
                f"is not accepted by Kafka: {ex}"
            ) from ex

        try:
            metadata = await asyncio.to_thread(
                admin_client.list_topics,
                timeout=_TOPIC_METADATA_TIMEOUT_SECONDS,
            )
        except KafkaException as ex:
            _logger.warning(
                "%s: could not check whether topic %r exists on %s: %s. "
                "Subscribing anyway.",
                self._config.processor_name,
                self._topic_to_subscribe,
                self._config.bootstrap_servers,
                ex,
            )
            return

        if self._topic_to_subscribe in metadata.topics:
            return

        _logger.warning(
            "%s: topic %r does not exist on %s. The consumer stays "
            "subscribed and starts reading as soon as the topic appears; "
            "until then it consumes nothing. Check the topic name if this "
            "is unexpected.",
            self._config.processor_name,
            self._topic_to_subscribe,
            self._config.bootstrap_servers,
        )

    async def start(self) -> None:
        """
        Checks the topic and subscribes the consumer to it.

        :raises KafkaConnectionError: if the consumer configuration is not
                                      accepted by Kafka.
        """
        await self._check_topic_is_available()

        self._consumer.subscribe(
            topics=[self._topic_to_subscribe],
            on_assign=self._connection_flag_method,
        )

    @staticmethod
    def message_is_empty(message: Any, consumer: Consumer) -> bool:
        """
        Checks if the Kafka message is empty or has a missing key.
        :param message: Kafka message object.
        :param consumer: Kafka consumer instance.

        :returns: True, if the message is empty or invalid, otherwise False.

        """
        if message is None:
            consumer.commit(asynchronous=True)
            return True

        if getattr(message, "key", None) is None:
            consumer.commit(asynchronous=True)
            return True

        if message.key() is None:
            consumer.commit(asynchronous=True)
            return True

        return False

    @staticmethod
    async def get_message(consumer: Consumer) -> Future:
        """
        Asynchronously polls a message from the Kafka topic.
        :param consumer: Kafka consumer instance.

        :returns: FutureAsync future
        """
        loop = asyncio.get_running_loop()
        poll = functools.partial(consumer.poll, 1.0)
        return await loop.run_in_executor(executor=None, func=poll)

    @abstractmethod
    async def process(self):
        """
        Abstract method to process Kafka messages.

        This method must be implemented in subclasses.
        """
        pass


def _safe_decode(raw: bytes | None) -> str:
    """
    Decode bytes to UTF-8 string for logging/storage.
    Non-UTF-8 bytes are replaced with the Unicode replacement character;
    None is returned as a placeholder string.
    """
    if raw is None:
        return "<none>"
    try:
        return raw.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        return raw.decode("utf-8", errors="replace")


def __check_redis_settings_with_request(
    consumer_config: ConsumerConfig, store_error_messages: bool
) -> None:
    if store_error_messages and consumer_config.redis_store_config is None:
        raise ConfigurationError(
            f"{consumer_config.processor_name}: store_error_messages is on "
            f"but redis_store_config is not set"
        )

    return


def kafka_processor(
    raise_error: bool = False,
    read_empty_messages: bool = False,
    store_error_messages: bool = True,
):
    """
    Decorator for handling Kafka processing errors.

    :param raise_error: If True, re-raises the caught exception.
    :param read_empty_messages: Skip processing if the message is empty and we're not allowed to read empty messages
    :param store_error_messages: If True, error messages data are stored in Redis.

    :return: A decorator for wrapping the Kafka consumer's `process` method.
    """
    logger = configure_logger("kafka_processor")

    def handle_kafka_errors(wrapped_function):
        async def wrapper(self, *args, **kwargs):
            __check_redis_settings_with_request(
                self._config, store_error_messages
            )

            redis_client = None
            message = None
            if store_error_messages:
                redis_client = (
                    self._config.redis_store_config.get_redis_client()
                )

            while True:
                try:
                    logger.debug("Polling for a message")
                    message = await self.get_message(self._consumer)
                    if self.message_is_empty(message, self._consumer):
                        if read_empty_messages:
                            message = None

                        else:
                            return
                    if message is not None:
                        # Coordinates only: the key is business data.
                        logger.debug(
                            "Start processing message: topic=%s partition=%s "
                            "offset=%s",
                            message.topic(),
                            message.partition(),
                            message.offset(),
                        )
                    await wrapped_function(self, message, *args, **kwargs)
                    logger.debug("Done processing")

                except Exception as ex:
                    __process_kafka_error_message(
                        self=self,
                        error_instance=ex,
                        raise_error=raise_error,
                        store_error_messages=store_error_messages,
                        redis_client=redis_client,
                        message=message,
                    )

                finally:
                    self._consumer.commit(asynchronous=True)

        return wrapper

    return handle_kafka_errors


def __process_kafka_error_message(
    self,
    error_instance: Exception,
    raise_error: bool,
    store_error_messages: bool,
    redis_client: Any,
    message: cimpl.Message | None,
):
    default_no_message = "<no message>"
    error_type = type(error_instance).__name__
    error_message = str(error_instance)
    error_datetime = str(datetime.datetime.now(datetime.timezone.utc))

    if raise_error:
        raise KafkaMessageError(error_message)

    msg_key = (
        _safe_decode(message.key())
        if message is not None
        else default_no_message
    )
    msg_value = (
        _safe_decode(message.value())
        if message is not None
        else default_no_message
    )
    msg_topic = message.topic() if message is not None else default_no_message
    msg_offset = message.offset() if message is not None else default_no_message
    msg_partition = (
        message.partition() if message is not None else default_no_message
    )

    if store_error_messages:
        redis_client.hset(
            error_datetime + "____" + str(uuid.uuid4()),
            mapping=RedisMessage(
                processor=self._config.processor_name,
                topic=self._config.topic_to_subscribe,
                error_message=error_message,
                error_type=error_type,
                error_datetime=error_datetime,
                message_key=msg_key,
                message_value=msg_value,
            ).__dict__,
        )
    # Neither the key nor the value is logged at any level: both are business
    # data and may carry personal data, tokens or identifiers. The coordinates
    # below are enough to find the message on the broker, and the payload
    # itself is kept in the Redis error store.
    _logger.error(
        "Kafka processing error in %s: %s: %s (topic=%s partition=%s "
        "offset=%s)",
        self._config.processor_name,
        error_type,
        error_message,
        msg_topic,
        msg_partition,
        msg_offset,
    )


def _close_consumer(task: ConsumerInitializer) -> None:
    """
    Releases the librdkafka client of a consumer that will not be used.

    Dropping the reference is not enough: the client keeps its own threads and
    sockets until it is closed, and they would stay for the whole life of the
    process.

    :param task: The consumer to close.
    """
    consumer = getattr(task, "_consumer", None)
    if consumer is None:
        return

    try:
        consumer.close()
    except Exception as ex:
        # A failure to clean up must not replace the error that caused it,
        # and closing an already closed client must stay harmless.
        _logger.debug("Could not close a Kafka client: %s", ex)


async def _start_consumers(
    tasks: list[ConsumerInitializer],
) -> list[ConsumerInitializer]:
    """
    Starts every consumer concurrently and drops the ones that failed.

    Starting in parallel keeps a slow metadata lookup from delaying the other
    consumers, and keeps one consumer that cannot start from preventing the
    rest from running. Only Kafka startup errors are treated that way: any
    other exception, including cancellation, is left to propagate rather than
    being turned into a silently missing consumer.

    Nothing is closed here. Every consumer passed in — started, failed or not
    reached at all — is closed by ``process_kafka_connection``, so that there
    is a single owner and cancellation cannot slip between the two.

    :param tasks: A list of initialized Kafka consumers.

    :returns: The consumers that started successfully, in the original order.

    :raises BaseException: whatever a consumer raised, if it is not a Kafka
                           startup error.
    """
    startable = [task for task in tasks if hasattr(task, "start")]
    results = await asyncio.gather(
        *[task.start() for task in startable], return_exceptions=True
    )

    failed = []
    for task, result in zip(startable, results):
        if not isinstance(result, BaseException):
            continue

        if not isinstance(result, _EXPECTED_START_ERRORS):
            raise result

        _logger.error(
            "Kafka consumer %s failed to start",
            task._config.processor_name,
            exc_info=result,
        )
        failed.append(task)

    return [task for task in tasks if task not in failed]


async def _stop_running(running: list[asyncio.Task]) -> None:
    """
    Cancels the processors still running and waits for all of them to finish.

    ``asyncio.gather`` propagates the first exception but leaves the other
    coroutines running, and the gather future is already done by then, so
    cancelling it does nothing. The tasks have to be held individually and
    cancelled one by one — otherwise the remaining processors keep polling
    their consumers while those consumers are being closed.

    :param running: The processor tasks of the current round.
    """
    for task in running:
        if not task.done():
            task.cancel()

    await asyncio.gather(*running, return_exceptions=True)


async def _run_processors(tasks: list[ConsumerInitializer]) -> None:
    """
    Polls every consumer concurrently until one of them stops or fails.

    :param tasks: The consumers that started successfully.
    """
    while True:
        running = [asyncio.ensure_future(task.process()) for task in tasks]

        try:
            await asyncio.gather(*running)

        finally:
            await _stop_running(running)


async def process_kafka_connection(tasks: list[ConsumerInitializer]) -> None:
    """
    Runs all Kafka consumer processors concurrently.

    Services normally schedule this coroutine with ``asyncio.create_task`` and
    never read its result. An exception leaving it would then be stored in the
    task object and never reach the logs, so the service would keep running
    with no consumer and no trace of why. Every exception is therefore logged
    here before it is re-raised.

    However the coroutine ends — an error, or the cancellation a service sends
    on shutdown — every consumer it was given is closed, so no librdkafka
    client outlives the connection. Closing covers all of ``tasks`` rather than
    only the ones that started: cancellation can arrive while they are still
    starting, and then there is no list of started consumers to close.

    :param tasks: A list of initialized Kafka consumers.

    :raises KafkaConnectionError: if none of the consumers could be started.
    """
    # Everything still owned by this connection. A consumer leaves the list
    # the moment it is closed, so nothing is closed twice and nothing is
    # forgotten — including when cancellation arrives mid-startup, before
    # there is any list of started consumers to close.
    to_close = list(tasks)

    try:
        started = await _start_consumers(tasks)

        # A consumer that will never run must not keep its client until the
        # connection ends: the healthy consumers may run for months.
        for task in tasks:
            if task not in started:
                _close_consumer(task)
                to_close.remove(task)

        if not started:
            raise KafkaConnectionError(
                "None of the Kafka consumers could be started"
            )

        await _run_processors(started)

    except Exception as ex:
        _logger.exception("Kafka consumer connection stopped: %s", ex)
        raise

    finally:
        for task in to_close:
            _close_consumer(task)


def init_kafka_connection(tasks: list[ConsumerInitializer]) -> None:
    """
    Initializes the asyncio event loop and starts Kafka consumer processing.

    :param tasks: A list of initialized Kafka consumers.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(process_kafka_connection(tasks=tasks))
    loop.run_forever()
