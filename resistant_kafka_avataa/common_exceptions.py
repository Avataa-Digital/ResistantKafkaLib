class ResistantKafkaError(Exception):
    """
    Base class of every error this package raises.

    It exists so that a consuming service can catch everything coming from
    this library with one clause instead of listing the concrete types:

        try:
            ...
        except ResistantKafkaError:
            ...

    Every exception below inherits from it, so adding this base changed
    nothing for code that already catches the concrete types or Exception.
    """

    pass


class TokenIsNotValid(ResistantKafkaError):
    """
    Raised, when received token is not valid
    """

    pass


class KafkaMessageError(ResistantKafkaError):
    """
    Raised when an error occurs during the message-consuming process
    """

    pass


class KafkaConnectionError(ResistantKafkaError):
    """
    Raised when an error occurs during the start consumer process
    """

    pass


class ConfigurationError(ResistantKafkaError):
    """
    Raised when the configuration the library was given cannot be used
    """

    pass


class MessageSerializationError(ResistantKafkaError, ValueError):
    """
    Raised when a message cannot be serialized for sending

    Also inherits ValueError, because up to 0.9.8b16 these failures were
    raised as a plain ValueError and a service may still be catching that.
    The ValueError parent is a compatibility bridge and is dropped in 0.10.0.
    """

    pass


class MessageDeserializationError(ResistantKafkaError, ValueError):
    """
    Raised when a consumed message cannot be deserialized

    Inherits ValueError for the same reason as MessageSerializationError, and
    with the same removal target.
    """

    pass
