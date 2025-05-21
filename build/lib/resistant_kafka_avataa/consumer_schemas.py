from typing import Union

from pydantic import BaseModel

from resistant_kafka_avataa.common_schemas import KafkaSecurityConfig, RedisStoreConfig


class ConsumerConfig(BaseModel):
    """
    Configuration settings for a Kafka consumer.

    :param topic_to_subscribe: Kafka topic that the processor will consume messages from.
    :param processor_name: Name of the processor, used mainly for logging purposes.
    :param bootstrap_servers: Kafka server addresses for connecting to the Kafka cluster.
    :param group_id: Consumer group ID, which identifies the consumer as subscribed to a specific topic.
                      Acceptable values: ['latest', 'earliest'].
    :param auto_offset_reset: Policy to set the consumer's position when the group is first created or
                               no previous offset is found. Can be set to 'latest' or 'earliest'.
    :param enable_auto_commit: If True, the Kafka consumer automatically commits message offsets at regular intervals
                               (e.g., every 5 seconds). If False, the offset is only committed after successful
                               message processing.
    """

    topic_to_subscribe: str
    processor_name: str
    bootstrap_servers: str
    group_id: str
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = True
    security_config: Union[KafkaSecurityConfig, None] = False
    redis_store_config: Union[RedisStoreConfig, None] = False
