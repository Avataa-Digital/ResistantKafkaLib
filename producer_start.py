from kafka_connection_utils import get_token_for_kafka_by_keycloak
from resistant_kafka_avataa import ProducerInitializer, ProducerConfig, DataSend
from resistant_kafka_avataa.common_schemas import KafkaSecurityConfig

security_config = KafkaSecurityConfig(
    oauth_cb=get_token_for_kafka_by_keycloak,
    security_protocol='SASL_PLAINTEXT',
    sasl_mechanisms='OAUTHBEARER'
)

task = ProducerInitializer(
    config=ProducerConfig(
        producer_name='KafkaTesterProducer1',
        bootstrap_servers='kafka.avataa.dev:9093',
        security_config=security_config
    )
)
task.send_message(
    data_to_send=DataSend(
        key='KEY1',
        value='VALUE1',
    )
)
task.send_message(
    data_to_send=DataSend(
        key='KEY1',
        value='WRONG_VALUE'
    )
)

task = ProducerInitializer(
    config=ProducerConfig(
        producer_name='KafkaTesterProducer2',
        bootstrap_servers='kafka.avataa.dev:9093',
        security_config=security_config
    ),

)
task.send_message(
    data_to_send=DataSend(
        key='KEY2',
        value='VALUE2',
        headers=[
            ('key_1', 'value_1'),
            ('key_2', 'value_2'),
        ]
    ))
