from confluent_kafka import Producer

from resistant_kafka_avataa.producer_schemas import ProducerConfig, DataSend


class ProducerInitializer:
    def __init__(
        self,
        config: ProducerConfig,
    ):
        """
        Initializes and manages a Kafka producer based on the given configuration.

        :param config: The configuration for the producer.
        """
        self._producer_name = config.producer_name
        self._producer = Producer(self._set_producer_config(config=config))

    @staticmethod
    def _set_producer_config(config: ProducerConfig) -> dict:
        """
        Prepares the dictionary of Kafka producer configuration based on the given settings.
        :param config: The consumer configuration.

        :returns: Dictionary of Kafka producer configuration parameters.
        """
        producer_config = {
            "bootstrap.servers": config.bootstrap_servers,
        }

        if config.security_config:
            producer_config["oauth_cb"] = config.security_config.oauth_cb
            producer_config["security.protocol"] = (
                config.security_config.security_protocol
            )
            producer_config["sasl.mechanisms"] = config.security_config.sasl_mechanisms

        return producer_config

    @staticmethod
    def _delivery_report(error_message, message) -> None:
        """
        Logs a message when the producer successfully sent to the topic.
        """
        if error_message is not None:
            print(
                "Delivery failed for User record {}: {}".format(
                    message.key(), error_message
                )
            )
            return

        print(
            "User record {} successfully produced to {} [{}] at offset {}".format(
                message.key(), message.topic(), message.partition(), message.offset()
            )
        )

    def send_message(
        self,
        data_to_send: DataSend,
        partition_number: int = 1,
    ) -> None:
        """
            Send message to Kafka topic.

        :param data_to_send: Data with configuration to send message to Kafka topic
        :param partition_number: Number for producer partition
        """
        self._producer.produce(
            topic=self._producer_name,
            key=data_to_send.key,
            value=data_to_send.value,
            on_delivery=self._delivery_report,
            headers=data_to_send.headers,
            partition=partition_number
        )
        self._producer.flush()
