"""Shared fixtures for consumer tests."""
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def redis_mock() -> MagicMock:
    """Redis client mock for error storage."""
    return MagicMock()


@pytest.fixture
def consumer_self_mock() -> MagicMock:
    """Consumer instance mock with _config (processor_name, topic_to_subscribe)."""
    mock = MagicMock()
    mock._config.processor_name = "test_processor"
    mock._config.topic_to_subscribe = "test-topic"
    return mock


def make_kafka_message(
    key: bytes = b"valid_key",
    value: bytes = b"valid_value",
    topic: str = "test-topic",
    offset: int = 12345,
) -> MagicMock:
    """Build a Kafka message mock with given key/value/topic/offset."""
    msg = MagicMock()
    msg.key.return_value = key
    msg.value.return_value = value
    msg.topic.return_value = topic
    msg.offset.return_value = offset
    return msg
