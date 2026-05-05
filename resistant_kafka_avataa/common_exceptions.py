class TokenIsNotValid(Exception):
    """
    Raised, when received token is not valid
    """

    pass


class KafkaMessageError(Exception):
    """
    Raised when an error occurs during the message-consuming process
    """

    pass


class KafkaConnectionError(Exception):
    """
    Raised when an error occurs during the start consumer process
    """

    pass
