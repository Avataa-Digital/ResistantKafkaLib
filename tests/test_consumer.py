from unittest.mock import MagicMock

import pytest

import resistant_kafka_avataa.consumer as consumer_module
from resistant_kafka_avataa.consumer import _safe_decode


_process_kafka_error_message = getattr(consumer_module, "__process_kafka_error_message")


def test_safe_decode_valid_utf8_returns_decoded_string() -> None:
    """Decode valid UTF-8 bytes to string including Cyrillic."""
    # Arrange
    raw: bytes = b"hello \xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82"

    # Act
    result: str = _safe_decode(raw)

    # Assert
    assert result == "hello Привет"


def test_safe_decode_none_returns_placeholder() -> None:
    """None is returned as placeholder string."""
    # Arrange / Act
    result: str = _safe_decode(None)

    # Assert
    assert result == "<none>"


def test_safe_decode_invalid_utf8_does_not_raise_returns_replacements() -> None:
    """Invalid UTF-8 bytes are decoded with replacement character (no UnicodeDecodeError)."""
    # Arrange — 0x91 is invalid UTF-8 start byte
    raw: bytes = b"abc\x91\xff\xfe"

    # Act
    result: str = _safe_decode(raw)

    # Assert
    assert isinstance(result, str)
    assert "\ufffd" in result


def test_safe_decode_empty_bytes_returns_empty_string() -> None:
    """Empty bytes decode to empty string."""
    # Arrange / Act
    result: str = _safe_decode(b"")

    # Assert
    assert result == ""


def test_process_kafka_error_message_with_invalid_utf8_value_does_not_raise(
    consumer_self_mock: MagicMock,
    redis_mock: MagicMock,
) -> None:
    """When message.value() is invalid UTF-8, error handler stores safe string and does not raise."""
    # Arrange
    message = MagicMock()
    message.key.return_value = b"valid_key"
    message.value.return_value = b"val\x91ue"  # 0x91 invalid start byte
    message.topic.return_value = "test-topic"
    message.offset.return_value = 12345

    # Act
    _process_kafka_error_message(
        self=consumer_self_mock,
        error_instance=ValueError("test error"),
        raise_error=False,
        store_error_messages=True,
        redis_client=redis_mock,
        message=message,
    )

    # Assert
    redis_mock.hset.assert_called_once()
    mapping = redis_mock.hset.call_args[1]["mapping"]
    assert mapping["message_key"] == "valid_key"
    assert isinstance(mapping["message_value"], str)
    assert "\ufffd" in mapping["message_value"]


def test_process_kafka_error_message_with_protobuf_like_value_does_not_raise(
    consumer_self_mock: MagicMock,
    redis_mock: MagicMock,
) -> None:
    """Real-world case: message.value() is binary (e.g. protobuf) — error at position 3, invalid start byte 0x91.
    Reproduces UnicodeDecodeError from production trace.
    """
    # Arrange — minimal prefix from real trace: b"\n\x1a\x08\x91\xc6\x99\x17\x12\x07..."
    # decode('utf-8') fails at byte 0x91 (position 3)
    protobuf_like_value: bytes = b"\n\x1a\x08\x91\xc6\x99\x17\x12\x074147218\x18\xff\x01"
    message = MagicMock()
    message.key.return_value = b"key"
    message.value.return_value = protobuf_like_value
    message.topic.return_value = "syslog-topic"
    message.offset.return_value = 42

    # Act — must not raise UnicodeDecodeError
    _process_kafka_error_message(
        self=consumer_self_mock,
        error_instance=ValueError("deserialization failed"),
        raise_error=False,
        store_error_messages=True,
        redis_client=redis_mock,
        message=message,
    )

    # Assert
    redis_mock.hset.assert_called_once()
    mapping = redis_mock.hset.call_args[1]["mapping"]
    assert mapping["message_key"] == "key"
    assert isinstance(mapping["message_value"], str)
    # Invalid bytes replaced; no exception
    assert "\ufffd" in mapping["message_value"] or len(mapping["message_value"]) > 0


def test_process_kafka_error_message_with_invalid_utf8_key_does_not_raise(
    consumer_self_mock: MagicMock,
    redis_mock: MagicMock,
) -> None:
    """When message.key() is invalid UTF-8, error handler stores safe string and does not raise."""
    # Arrange
    message = MagicMock()
    message.key.return_value = b"key\x91\xff"
    message.value.return_value = b"valid_value"
    message.topic.return_value = "t"
    message.offset.return_value = 0

    # Act
    _process_kafka_error_message(
        self=consumer_self_mock,
        error_instance=RuntimeError("err"),
        raise_error=False,
        store_error_messages=True,
        redis_client=redis_mock,
        message=message,
    )

    # Assert
    mapping = redis_mock.hset.call_args[1]["mapping"]
    assert isinstance(mapping["message_key"], str)
    assert mapping["message_value"] == "valid_value"


def test_process_kafka_error_message_with_none_message_does_not_raise(
    consumer_self_mock: MagicMock,
    redis_mock: MagicMock,
) -> None:
    """When message is None (e.g. error before poll), error handler uses placeholders."""
    # Arrange
    # Act
    _process_kafka_error_message(
        self=consumer_self_mock,
        error_instance=ValueError("no message"),
        raise_error=False,
        store_error_messages=True,
        redis_client=redis_mock,
        message=None,
    )

    # Assert
    mapping = redis_mock.hset.call_args[1]["mapping"]
    assert mapping["message_key"] == "<no message>"
    assert mapping["message_value"] == "<no message>"
