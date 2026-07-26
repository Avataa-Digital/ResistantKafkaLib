from resistant_kafka_avataa.common_schemas import KafkaSecurityConfig
from resistant_kafka_avataa.consumer import ConsumerInitializer
from resistant_kafka_avataa.consumer_schemas import ConsumerConfig
from resistant_kafka_avataa.producer import ProducerInitializer
from resistant_kafka_avataa.producer_schemas import ProducerConfig


def _base_security_config() -> KafkaSecurityConfig:
    return KafkaSecurityConfig(
        security_protocol="SASL_SSL",
        sasl_mechanisms="OAUTHBEARER",
    )


def test_to_confluent_extra_without_optional_fields_returns_empty_dict() -> (
    None
):
    """When no optional fields are set, to_confluent_extra returns an empty dict."""
    # Arrange
    config: KafkaSecurityConfig = _base_security_config()

    # Act
    result: dict = config.to_confluent_extra()

    # Assert
    assert result == {}


def test_to_confluent_extra_maps_ssl_fields_to_confluent_keys() -> None:
    """SSL fields are mapped to confluent-kafka ssl.* config keys."""
    # Arrange
    config: KafkaSecurityConfig = KafkaSecurityConfig(
        security_protocol="SSL",
        sasl_mechanisms="",
        ssl_ca_location="/etc/kafka/ca.pem",
        ssl_certificate_location="/etc/kafka/client.crt",
        ssl_key_location="/etc/kafka/client.key",
        ssl_key_password="secret",
    )

    # Act
    result: dict = config.to_confluent_extra()

    # Assert
    assert result == {
        "ssl.ca.location": "/etc/kafka/ca.pem",
        "ssl.certificate.location": "/etc/kafka/client.crt",
        "ssl.key.location": "/etc/kafka/client.key",
        "ssl.key.password": "secret",
    }


def test_to_confluent_extra_maps_oauthbearer_fields() -> None:
    """SASL OAuthBearer fields are mapped to sasl.oauthbearer.* config keys."""
    # Arrange
    config: KafkaSecurityConfig = KafkaSecurityConfig(
        security_protocol="SASL_SSL",
        sasl_mechanisms="OAUTHBEARER",
        sasl_oauthbearer_method="oidc",
        sasl_oauthbearer_client_id="client-id",
        sasl_oauthbearer_client_secret="client-secret",
        sasl_oauthbearer_token_endpoint_url="https://auth.example.com/token",
        sasl_oauthbearer_scope="kafka",
    )

    # Act
    result: dict = config.to_confluent_extra()

    # Assert
    assert result == {
        "sasl.oauthbearer.method": "oidc",
        "sasl.oauthbearer.client.id": "client-id",
        "sasl.oauthbearer.client.secret": "client-secret",
        "sasl.oauthbearer.token.endpoint.url": "https://auth.example.com/token",
        "sasl.oauthbearer.scope": "kafka",
    }


def test_producer_config_includes_ssl_fields_when_set() -> None:
    """ProducerInitializer passes SSL certificate paths into confluent config."""
    # Arrange
    config: ProducerConfig = ProducerConfig(
        producer_name="test-topic",
        bootstrap_servers="localhost:9093",
        security_config=KafkaSecurityConfig(
            security_protocol="SSL",
            sasl_mechanisms="",
            ssl_ca_location="/ca.pem",
            ssl_certificate_location="/cert.pem",
            ssl_key_location="/key.pem",
        ),
    )

    # Act
    result: dict = ProducerInitializer._set_producer_config(config=config)

    # Assert
    assert result["security.protocol"] == "SSL"
    assert result["ssl.ca.location"] == "/ca.pem"
    assert result["ssl.certificate.location"] == "/cert.pem"
    assert result["ssl.key.location"] == "/key.pem"
    assert "ssl.key.password" not in result


def test_consumer_config_includes_ssl_fields_when_set() -> None:
    """ConsumerInitializer passes SSL certificate paths into confluent config."""
    # Arrange
    config: ConsumerConfig = ConsumerConfig(
        topic_to_subscribe="test-topic",
        processor_name="test-processor",
        bootstrap_servers="localhost:9093",
        group_id="test-group",
        auto_offset_reset="latest",
        enable_auto_commit=False,
        security_config=KafkaSecurityConfig(
            security_protocol="SASL_SSL",
            sasl_mechanisms="SCRAM-SHA-512",
            ssl_ca_location="/ca.pem",
            ssl_key_password="pass",
        ),
    )

    # Act
    result: dict = ConsumerInitializer._set_consumer_config(config=config)

    # Assert
    assert result["security.protocol"] == "SASL_SSL"
    assert result["sasl.mechanisms"] == "SCRAM-SHA-512"
    assert result["ssl.ca.location"] == "/ca.pem"
    assert result["ssl.key.password"] == "pass"
    assert "ssl.certificate.location" not in result
