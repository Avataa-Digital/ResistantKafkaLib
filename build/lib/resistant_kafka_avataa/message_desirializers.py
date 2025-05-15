from collections import defaultdict
from logging import getLogger
from typing import Any, Optional, Type

from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.protobuf import ProtobufDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField
from google.protobuf import json_format

_SCHEMA_REGISTRY_VALUE_FLAG = 0
_SCHEMA_REGISTRY_SERVICE_VALUES = 7

class MessageDeserializer:
    """
        This class is used to deserialize messages from Kafka.
    """
    def __init__(self, topic: str, schema_registry_url: str | None = None, ):
        self.schema_registry_client = None
        self.topic = topic
        self.deserializers: dict[
            str, dict[str, Optional[ProtobufDeserializer, DefaultMessageDeserializer]]] = defaultdict(dict)
        self.proto_deserializers: dict = dict()
        self.logger = getLogger("Message Handler")

        if schema_registry_url:
            self.schema_registry_client = SchemaRegistryClient(
                {
                    "url": schema_registry_url,
                    "timeout": 5,
                }
            )

    def register_protobuf_deserializer(
            self, message_type: Type[Any],
    ) -> None:
        """
            According to the message type, register a deserializer for a topic by deserializer:
                - custom (by added files in "deserializers" attribute)
                - default (by adding "DefaultMessageDeserializer", which serializes messages as string)
        """
        if self.schema_registry_client:
            self.deserializers[self.topic][message_type.__name__] = ProtobufDeserializer(
                message_type=message_type,
                schema_registry_client=self.schema_registry_client,
                conf={"use.deprecated.format": False},
            )

        else:
            self.deserializers[self.topic][message_type.__name__] = DefaultMessageDeserializer(
                message_type=message_type,
            )
        self.proto_deserializers[message_type.__name__] = message_type

        self.logger.info(
            f"Registered new deserializer for topic {self.topic} and key {message_type.__name__}"
        )

    def deserialize(
            self,
            message: Any,
    ) -> Any:
        """
            Main function for deserialization messages from Kafka.
            Using this method, you get a message as an object, from proto format
        """
        key = (
            "List" + message.key().decode("utf-8").split(":")[0]
            if message.key()
            else "unknown"
        )

        not_registered_topic = self.topic not in self.deserializers or key not in self.deserializers[self.topic]

        if not_registered_topic:
            raise ValueError(f"No deserializer registered for topic {self.topic}")

        deserializer = self.deserializers[self.topic][key]
        return deserializer(message.value(), SerializationContext(self.topic, MessageField.VALUE))

    def deserialize_to_dict(self, message: Any):
        """
            This method returns a message as a dictionary, from proto format
        """
        key = (
            "List" + message.key().decode("utf-8").split(":")[0]
            if message.key()
            else "unknown"
        )

        deserializer = self.proto_deserializers[key]()
        message_value = message.value()
        if message_value[0] == _SCHEMA_REGISTRY_VALUE_FLAG:
            message_value = message_value[_SCHEMA_REGISTRY_SERVICE_VALUES:]

        deserializer.ParseFromString(message_value)
        return json_format.MessageToDict(
            deserializer,
            including_default_value_fields=False,
            preserving_proto_field_name=True,
        )

class DefaultMessageDeserializer:
    """
        This class deserializes messages as string
        Also clear messages from kafka service information
    """
    def __init__(self, message_type: Any) -> None:
        self.message_type = message_type
        self.logger = getLogger("Manual Deserializer")

    def _remove_schema_registry_flags(self, message: bytes) -> bytes:
        """
            If a schema registry flag is set, remove kafka service info from a message
        """
        if message[0] == _SCHEMA_REGISTRY_VALUE_FLAG:
            return message[_SCHEMA_REGISTRY_SERVICE_VALUES:]

        return message

    def __call__(self, message: bytes, ctx: Optional[SerializationContext] = None):
        """
             Looks like ProtobufDeserializer from confluent_kafka.schema_registry.protobuf.
             So we have to use by default "ctx" attribute
        """
        self.logger.info("Deserialized with help manual")
        message = self._remove_schema_registry_flags(message=message)

        message_type = self.message_type()

        try:
            message_type.ParseFromString(message)
            return message_type

        except Exception as ex:
            self.logger.info(type(ex))
            self.logger.exception(ex)
            raise ValueError("Incorrect message")
