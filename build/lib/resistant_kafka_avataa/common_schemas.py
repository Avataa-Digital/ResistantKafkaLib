from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel
from redis import Redis


class KafkaSecurityConfig(BaseModel):
    """
    Security configuration settings for a Kafka consumer. Uses as part for main config classes.

    :param oauth_cb: A function that returns a token for authentication.
                            Required only if `secured` is True.
    :param security_protocol: The protocol used to communicate with Kafka brokers
                              (e.g., 'SASL_PLAINTEXT', 'SASL_SSL').
    :param sasl_mechanisms: The SASL mechanism used for authentication (e.g., 'PLAIN', 'SCRAM-SHA-256').
    :param error_cb: A function that returns an error during the authentication.
    Accordance KIP-1139
    :param sasl_oauthbearer_method: The SASL OAuth mechanism used for authentication.
    :param sasl_oauthbearer_client_id: The SASL OAuth client id used for authentication.
    :param sasl_oauthbearer_client_secret: The SASL OAuth client secret used for authentication.
    :param sasl_oauthbearer_token_endpoint_url: The SASL OAuth token endpoint URL.
    :param sasl_oauthbearer_scope: The SASL OAuth scope used for authentication.
    """

    oauth_cb: Callable | None = None
    security_protocol: str
    sasl_mechanisms: str
    error_cb: Callable | None = None
    sasl_oauthbearer_method: str | None = None
    sasl_oauthbearer_client_id: str | None = None
    sasl_oauthbearer_client_secret: str | None = None
    sasl_oauthbearer_token_endpoint_url: str | None = None
    sasl_oauthbearer_scope: str | None = None


class RedisStoreConfig(BaseModel):
    """
    :param host: Redis host
    :param port: Redis port
    :param decode_responses: Receive decoded strings
    :param db: Redis database id
    """

    host: str
    port: int
    decode_responses: bool
    db: int

    def get_redis_client(self) -> Redis:
        return Redis(
            host=self.host,
            port=self.port,
            decode_responses=self.decode_responses,
            db=self.db,
        )


@dataclass
class RedisMessage:
    """
    This class is used to format error messages for Redis storage.

    :param processor: Name of the handler processing the specific topic.
    :param topic: Kafka topic from which the error message was received.
    :param error_message: Detailed message explaining why the error was raised.
    :param error_type: Type of the error (e.g., ValueError, TypeError).
    :param error_datetime: The time when the error occurred.
    :param message_key: Kafka message key.
    :param message_value: Kafka message value.
    """

    processor: str
    topic: str
    error_message: str
    error_type: str
    error_datetime: str
    message_key: str
    message_value: str
