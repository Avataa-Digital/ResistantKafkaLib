from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel
from redis import Redis

_SECURITY_OPTIONAL_CONFLUENT_MAPPING: dict[str, str] = {
    "sasl_oauthbearer_method": "sasl.oauthbearer.method",
    "sasl_oauthbearer_client_id": "sasl.oauthbearer.client.id",
    "sasl_oauthbearer_client_secret": "sasl.oauthbearer.client.secret",
    "sasl_oauthbearer_token_endpoint_url": "sasl.oauthbearer.token.endpoint.url",
    "sasl_oauthbearer_scope": "sasl.oauthbearer.scope",
    "ssl_ca_location": "ssl.ca.location",
    "ssl_certificate_location": "ssl.certificate.location",
    "ssl_key_location": "ssl.key.location",
    "ssl_key_password": "ssl.key.password",
}


class KafkaSecurityConfig(BaseModel):
    """
    Security configuration settings for a Kafka consumer/producer.

    :param oauth_cb: A function that returns a token for authentication.
                            Required only if `secured` is True.
    :param security_protocol: The protocol used to communicate with Kafka brokers
                              (e.g., 'SASL_PLAINTEXT', 'SASL_SSL', 'SSL').
    :param sasl_mechanisms: The SASL mechanism used for authentication (e.g., 'PLAIN', 'SCRAM-SHA-256').
    :param error_cb: A function that returns an error during the authentication.
    Accordance KIP-1139
    :param sasl_oauthbearer_method: The SASL OAuth mechanism used for authentication.
    :param sasl_oauthbearer_client_id: The SASL OAuth client id used for authentication.
    :param sasl_oauthbearer_client_secret: The SASL OAuth client secret used for authentication.
    :param sasl_oauthbearer_token_endpoint_url: The SASL OAuth token endpoint URL.
    :param sasl_oauthbearer_scope: The SASL OAuth scope used for authentication.
    :param ssl_ca_location: Path to CA certificate file (maps to ssl.ca.location).
    :param ssl_certificate_location: Path to client certificate file (maps to ssl.certificate.location).
    :param ssl_key_location: Path to client private key file (maps to ssl.key.location).
    :param ssl_key_password: Password for the client private key (maps to ssl.key.password).
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
    ssl_ca_location: str | None = None
    ssl_certificate_location: str | None = None
    ssl_key_location: str | None = None
    ssl_key_password: str | None = None

    def to_confluent_extra(self) -> dict[str, Any]:
        """Return optional confluent-kafka config entries derived from this security config."""
        result: dict[str, Any] = {}
        for attr, confluent_key in _SECURITY_OPTIONAL_CONFLUENT_MAPPING.items():
            value = getattr(self, attr)
            if value:
                result[confluent_key] = value
        return result


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
