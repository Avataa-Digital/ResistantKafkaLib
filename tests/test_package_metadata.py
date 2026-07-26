"""Tests guarding the packaging contract: single source of version and declared deps."""

from importlib.metadata import requires, version

import resistant_kafka_avataa


def test_dunder_version_matches_installed_distribution() -> None:
    """__version__ comes from the installed distribution, never from a hardcode."""
    # Arrange / Act
    installed = version("resistant_kafka_avataa")

    # Assert
    assert resistant_kafka_avataa.__version__ == installed


def test_redis_is_a_declared_dependency() -> None:
    """redis is declared in the metadata: it is imported at module level."""
    # Arrange / Act
    declared = requires("resistant_kafka_avataa") or []

    # Assert
    assert any(spec.startswith("redis") for spec in declared)


def test_public_api_names_are_importable() -> None:
    """Every name in __all__ is really available as a package attribute."""
    # Arrange
    exported: list[str] = resistant_kafka_avataa.__all__

    # Act / Assert
    for name in exported:
        assert hasattr(resistant_kafka_avataa, name), name
