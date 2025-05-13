from kafka_connection_utils import get_token_for_kafka_by_keycloak
from resistant_kafka_avataa.common_schemas import KafkaSecurityConfig, RedisStoreConfig
from resistant_kafka_avataa.consumer_schemas import ConsumerConfig
from resistant_kafka_avataa.consumer import ConsumerInitializer, kafka_processor, init_kafka_connection

consumer_config = KafkaSecurityConfig(
    oauth_cb=get_token_for_kafka_by_keycloak,
    security_protocol='SASL_PLAINTEXT',
    sasl_mechanisms='OAUTHBEARER'
)

redis_store_config = RedisStoreConfig(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True,
)


class KafkaMessage1Processor(ConsumerInitializer):
    def __init__(
            self, config: ConsumerConfig
    ):
        super().__init__(config=config)
        self._config = config

    @kafka_processor(read_empty_messages=False, store_error_messages=True)
    async def process(self, message):
        message_key = message.key().decode("utf-8")
        message_value = message.value().decode("utf-8")

        if message_value in ['WRONG_VALUE']:
            raise ValueError('You catch wrong value')

        print('-----------------------------')
        print('KEY', message_key)
        print('VALUE', message_value)
        print('CONSUMER', self._config.topic_to_subscribe)
        print('-----------------------------')


class KafkaMessage2Processor(ConsumerInitializer):
    def __init__(
            self,
            config: ConsumerConfig
    ):
        super().__init__(config=config)
        self._config = config

    @kafka_processor()
    async def process(self, message):
        message_key = message.key().decode("utf-8")
        message_value = message.value().decode("utf-8")

        print('-----------------------------')
        print('KEY', message_key)
        print('VALUE', message_value)
        print('PRODUCER', self._config.topic_to_subscribe)
        print('-----------------------------')


process_task_1 = KafkaMessage1Processor(
    config=ConsumerConfig(
        topic_to_subscribe='KafkaTesterProducer1',
        processor_name='KafkaProcessor1',
        bootstrap_servers='kafka.avataa.dev:9093',
        group_id='LocalTester1',
        auto_offset_reset='latest',
        enable_auto_commit=False,
        security_config=consumer_config,
        redis_store_config=redis_store_config,
    )
)

process_task_2 = KafkaMessage2Processor(
    config=ConsumerConfig(
        topic_to_subscribe='KafkaTesterProducer2',
        processor_name='KafkaProcessor2',
        bootstrap_servers='kafka.avataa.dev:9093',
        group_id='LocalTester1',
        auto_offset_reset='latest',
        enable_auto_commit=False,
        security_config=consumer_config,
        redis_store_config=redis_store_config,
    )
)

init_kafka_connection(
    tasks=[process_task_1, process_task_2]
)



