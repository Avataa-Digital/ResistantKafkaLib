from importlib.metadata import version as _package_version

from .common_exceptions import (
    ConfigurationError,
    KafkaConnectionError,
    KafkaMessageError,
    MessageDeserializationError,
    MessageSerializationError,
    ResistantKafkaError,
    TokenIsNotValid,
)
from .consumer import (
    ConsumerInitializer,
    init_kafka_connection,
    kafka_processor,
)
from .consumer_schemas import ConsumerConfig
from .producer import ProducerInitializer
from .producer_schemas import ProducerConfig, DataSend

# Single source of the version is pyproject.toml: here it is read from the
# installed distribution's metadata, so the two can never drift apart.
__version__ = _package_version("resistant_kafka_avataa")

__all__ = [
    "ConsumerInitializer",
    "init_kafka_connection",
    "kafka_processor",
    "ConsumerConfig",
    "ProducerInitializer",
    "ProducerConfig",
    "DataSend",
    # The exception contract: everything this package raises inherits from
    # ResistantKafkaError, so one clause is enough to catch it all.
    "ResistantKafkaError",
    "ConfigurationError",
    "KafkaConnectionError",
    "KafkaMessageError",
    "MessageDeserializationError",
    "MessageSerializationError",
    "TokenIsNotValid",
]
