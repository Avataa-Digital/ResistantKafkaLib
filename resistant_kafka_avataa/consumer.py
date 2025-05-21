import asyncio
import datetime
import functools
import logging
import uuid
from abc import abstractmethod
from asyncio import Future
from typing import Any

from confluent_kafka import Consumer

from resistant_kafka_avataa.common_exceptions import KafkaMessageError
from resistant_kafka_avataa.common_schemas import RedisMessage
from resistant_kafka_avataa.consumer_schemas import ConsumerConfig
from resistant_kafka_avataa.message_desirializers import MessageDeserializer

logging.basicConfig(level=logging.INFO)


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
        self._consumer.subscribe(
            topics=[config.topic_to_subscribe], on_assign=self._connection_flag_method
        )
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
            consumer_config["oauth_cb"] = config.security_config.oauth_cb
            consumer_config["security.protocol"] = (
                config.security_config.security_protocol
            )
            consumer_config["sasl.mechanisms"] = config.security_config.sasl_mechanisms

        return consumer_config

    def _connection_flag_method(self, *args) -> None:
        """
        Logs a message when the consumer has successfully subscribed to the topic.
        """
        logging.info(
            f"{self._config.processor_name} successfully subscribed "
            f"to the topic {self._config.topic_to_subscribe}\n"
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


def __check_redis_settings_with_request(
    consumer_config: ConsumerConfig, store_error_messages: bool
) -> None:
    if store_error_messages and consumer_config.redis_store_config is None:
        raise Exception("Redis store is not configured")

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

    def handle_kafka_errors(wrapped_function):
        async def wrapper(self, *args, **kwargs):
            __check_redis_settings_with_request(self._config, store_error_messages)

            redis_client = None
            message = None
            if store_error_messages:
                redis_client = self._config.redis_store_config.get_redis_client()

            while True:
                try:
                    message = await self.get_message(self._consumer)

                    if self.message_is_empty(message, self._consumer):
                        if read_empty_messages:
                            message = None

                        else:
                            return

                    await wrapped_function(self, message, *args, **kwargs)

                except Exception as e:
                    __process_kafka_error_message(
                        self=self,
                        error_instance=e,
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
    message: Any,
):
    error_type = type(error_instance).__name__
    error_message = str(error_instance)
    error_datetime = str(datetime.datetime.utcnow())

    if raise_error:
        raise KafkaMessageError(error_message)

    if store_error_messages:
        redis_client.hset(
            error_datetime + "____" + str(uuid.uuid4()),
            mapping=RedisMessage(
                processor=self._config.processor_name,
                topic=self._config.topic_to_subscribe,
                error_message=error_message,
                error_type=error_type,
                error_datetime=error_datetime,
                message_key=str(message.key().decode("utf-8")),
                message_value=str(message.value().decode("utf-8")),
            ).__dict__,
        )

    print(f"Kafka processing error: {error_type}: {error_message}")


async def process_kafka_connection(tasks: list[ConsumerInitializer]) -> None:
    """
    Runs all Kafka consumer processors concurrently.

    :param tasks: A list of initialized Kafka consumers.
    """
    while True:
        await asyncio.gather(*[task.process() for task in tasks])


def init_kafka_connection(tasks: list[ConsumerInitializer]) -> None:
    """
    Initializes the asyncio event loop and starts Kafka consumer processing.

    :param tasks: A list of initialized Kafka consumers.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(process_kafka_connection(tasks=tasks))
    loop.run_forever()
