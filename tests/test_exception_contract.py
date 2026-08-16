"""The exception hierarchy is a public contract: one base, catchable as one."""

import ast
import pathlib

import pytest

import resistant_kafka_avataa
from resistant_kafka_avataa import common_exceptions
from resistant_kafka_avataa.common_exceptions import (
    ConfigurationError,
    KafkaConnectionError,
    KafkaMessageError,
    MessageDeserializationError,
    MessageSerializationError,
    ResistantKafkaError,
    TokenIsNotValid,
)
from resistant_kafka_avataa.consumer_schemas import ConsumerConfig


PACKAGE_EXCEPTIONS = [
    ConfigurationError,
    KafkaConnectionError,
    KafkaMessageError,
    MessageDeserializationError,
    MessageSerializationError,
    TokenIsNotValid,
]

PACKAGE_ROOT = pathlib.Path(resistant_kafka_avataa.__file__).parent

#: Names this package is allowed to raise: its own exceptions, plus the ones
#: that must never be swallowed or replaced.
ALLOWED_RAISED_NAMES = {
    name for name in dir(common_exceptions) if not name.startswith("_")
} | {
    "asyncio.CancelledError",
    "CancelledError",
    "SystemExit",
    "KeyboardInterrupt",
}


def raised_names(source: pathlib.Path) -> set[str]:
    """Collect the names of exception types raised literally in a module."""
    found = set()

    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue

        raised = node.exc
        # `raise ex` re-raises a value: which type it is cannot be known here.
        if not isinstance(raised, ast.Call):
            continue

        if isinstance(raised.func, ast.Name):
            found.add(raised.func.id)
        elif isinstance(raised.func, ast.Attribute):
            found.add(raised.func.attr)

    return found


_check_redis_settings = getattr(
    resistant_kafka_avataa.consumer,
    "__check_redis_settings_with_request",
)


@pytest.mark.parametrize("exception_type", PACKAGE_EXCEPTIONS)
def test_every_exception_inherits_the_package_base(exception_type) -> None:
    """One except clause is enough to catch anything the package raises."""
    # Arrange / Act / Assert
    assert issubclass(exception_type, ResistantKafkaError)


@pytest.mark.parametrize("exception_type", PACKAGE_EXCEPTIONS)
def test_every_exception_is_still_catchable_on_its_own(exception_type) -> None:
    """Adding the base did not break code that catches the concrete type."""
    # Arrange / Act / Assert
    with pytest.raises(exception_type):
        raise exception_type("boom")


@pytest.mark.parametrize(
    "module_path",
    sorted(PACKAGE_ROOT.glob("*.py")),
    ids=lambda path: path.name,
)
def test_module_raises_only_package_exceptions(module_path) -> None:
    """No module raises a type a consumer cannot catch by the package base.

    Checking the raise sites one by one is what let three ValueError raises
    survive the introduction of the contract; this walks the whole package.
    """
    # Arrange / Act
    foreign = raised_names(module_path) - ALLOWED_RAISED_NAMES

    # Assert
    assert not foreign, (
        f"{module_path.name} raises {sorted(foreign)}, which "
        f"`except ResistantKafkaError` will not catch"
    )


def test_bridged_exceptions_still_catchable_as_value_error() -> None:
    """The types that used to be ValueError keep being catchable as one."""
    # Arrange / Act / Assert
    for exception_type in (
        MessageSerializationError,
        MessageDeserializationError,
    ):
        assert issubclass(exception_type, ValueError)
        assert issubclass(exception_type, ResistantKafkaError)


def test_base_is_exported_from_the_package_root() -> None:
    """The base is importable from the package, not only from the submodule."""
    # Arrange / Act / Assert
    assert resistant_kafka_avataa.ResistantKafkaError is ResistantKafkaError
    assert "ResistantKafkaError" in resistant_kafka_avataa.__all__


def test_missing_redis_config_raises_a_package_exception() -> None:
    """A misconfiguration is reported as ConfigurationError, not bare Exception."""
    # Arrange
    config = ConsumerConfig(
        topic_to_subscribe="documents.changes",
        processor_name="DocumentsChangesProcessor",
        bootstrap_servers="localhost:9092",
        group_id="test-group",
    )
    config.redis_store_config = None

    # Act / Assert — catchable by the base, as the contract promises
    with pytest.raises(ResistantKafkaError) as caught:
        _check_redis_settings(consumer_config=config, store_error_messages=True)

    assert isinstance(caught.value, ConfigurationError)
    assert "DocumentsChangesProcessor" in str(caught.value)
