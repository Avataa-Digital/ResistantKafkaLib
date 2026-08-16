from typing import Any

from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.protobuf import ProtobufSerializer
from confluent_kafka.serialization import SerializationContext, MessageField

from resistant_kafka_avataa.common_exceptions import (
    MessageSerializationError,
)
from resistant_kafka_avataa.logger import configure_logger


class MessageSerializer:
    """
    This class is used to serialize messages from Kafka producer by shema registry or just converting to string.
    """

    __DEFAULT_REGISTRY_CONFIG: dict[str, bool] = {
        "use.deprecated.format": False
    }

    def __init__(self, topic: str, schema_registry_url: str = None):

        self._schema_registry_url = schema_registry_url
        self._topic = topic
        self.serializers = dict()

        if schema_registry_url:
            self._schema_registry_client = SchemaRegistryClient(
                {
                    "url": self._schema_registry_url,
                    "timeout": 5,
                }
            )

        self.logger = configure_logger(__name__)

    def register_protobuf_serializer(self, message_type: Any) -> None:
        if self._schema_registry_url:
            self.serializers[message_type.__name__] = ProtobufSerializer(
                schema_registry_client=self._schema_registry_client,
                conf=self.__DEFAULT_REGISTRY_CONFIG,
                msg_type=message_type,
            )

            self.logger.info(
                "Registered new serializer for key %s", message_type.__name__
            )

    def serialize(self, message_to_send: Any, class_name: str | None = None):
        if self._schema_registry_url:
            serializer = self.serializers.get(class_name)

            if serializer:
                return serializer(
                    message_to_send,
                    SerializationContext(self._topic, MessageField.VALUE),
                )
            raise MessageSerializationError(
                f"No serializer registered for key {class_name}"
            )

        return message_to_send.SerializeToString()
