# Resistant Kafka

**Resistant Kafka** is a Python library designed to simplify and stabilize interactions with Apache Kafka, both as a
producer and a consumer.

## Features

### 🔌 Easy integration into any Python service

To connect a consumer or producer, you just need to create _**one instance of the corresponding class**_:
ConsumerInitializer
or ProducerInitializer.

###

### 🔁 Serialisation | Deserialisation

The library allows you to serialize and deserialize data that 
you send using .proto formats. It also supports Schema Registry, 
which allows you to make sure that the data arrives in the correct format.

###

### 💾 Redis integration

We provide an easy way to connect to Redis.
It is used for storing error messages and retrieving full information about each message.

###

### 🧾 Built-in logging of errors and events

Everything the package writes goes to standard `logging` loggers under the single
`resistant_kafka_avataa` prefix — subscription and topic checks from the consumer,
delivery reports from the producer, deserializer registration. Nothing is written to
stdout with `print`.

Configure it like any other library logger:

```commandline
import logging

logging.getLogger("resistant_kafka_avataa").setLevel(logging.WARNING)
```

The level can also be set with the `RESISTANT_KAFKA_LOG_LEVEL` environment variable
(default `INFO`).

**If your service has not configured logging at all**, the package falls back to
writing its own records to stderr, so warnings are not lost. That fallback switches
itself off the moment any handler of yours can receive the record, so the lines are
never printed twice — you do not have to choose between the two.

Two things are deliberately kept at `DEBUG` and are therefore invisible by default:

- the **body of a failed message**, because it may contain personal data or tokens.
  The error line itself always carries the topic, offset, key, error type and error
  text; only the value is held back;
- the **per-message delivery confirmation** from the producer, which would otherwise
  be one line for every message sent.

```commandline
logging.getLogger("resistant_kafka_avataa").setLevel(logging.DEBUG)
```

> ⚠️ **Note for existing users.** Up to and including `0.9.8b16` importing this package
> called `logging.basicConfig()`, which configured the **root** logger of the host
> process. A library has no business doing that, and the call is being removed. It is
> still present in this release, because for services that never configure logging
> themselves it is the only reason their own `INFO` records are visible at all —
> removing it without warning would silence the service, not just this package. Add
> `logging.basicConfig(level=logging.INFO)` (or your own configuration) to your
> application's entry point; the next release drops the call.

###

### 🧯 Errors you can catch

Everything this package raises inherits from a single base, so one clause is enough:

```commandline
from resistant_kafka_avataa import ResistantKafkaError

try:
    ...
except ResistantKafkaError:
    ...
```

| Exception | Raised when |
|---|---|
| `ResistantKafkaError` | base of all of them — never raised directly |
| `KafkaConnectionError` | a consumer could not be started |
| `KafkaMessageError` | processing a message failed and `raise_error=True` |
| `ConfigurationError` | the configuration given to the library cannot be used |
| `MessageSerializationError` | a message could not be serialized for sending |
| `MessageDeserializationError` | a consumed message could not be deserialized |
| `TokenIsNotValid` | the received token did not pass verification |

The base was added in `0.9.8b17` as a parent of the classes that already existed, so
`except KafkaConnectionError` and `except Exception` keep working unchanged.

The two serialization errors replace the plain `ValueError` those code paths raised up
to `0.9.8b16`. They inherit **both** the base and `ValueError`, so existing
`except ValueError` around serializing or deserializing keeps working. That second
parent is a compatibility bridge and is removed in `0.10.0` — move such handlers to
`ResistantKafkaError` before then.

Exception messages carry the processor name, the topic and the message coordinates —
never the message key or its payload.

###

### 🛡️ Resilience against consumer-side crashes

If an exception raises in the processor when reading a specific topic, by default, a detailed log about the dropped
message
will be issued and the consumer will continue its work.

In case you need to stop reading topic and raise exception - this option has also been added.

###

### 🧩 Handler creation for each topic in your service (Asynchronous)

One of the problems of working in the consumer _**is the case where the service reads several topics at the same time**_
and
this happens synchronously and in one handler.

**We solved this problem!**

By adding asynchronous reading of topics and adding the ability to read topics independently of
each other. Even if one of them crashes _(a crash will occur if you set the raise_error=True attribute in the
kafka_processor)_ - the other handler will continue its work.

Also in this case it is very easy to separate the logic of processing messages of different topics if their keys,
message type differ from each other.

###

# Consumer Initializer

## First Step. Add enviroments

Using the **_ConsumerConfig_** scheme you can configure the message reading handler in your service.

_If reading of several topics is expected, then a more convenient way is to assemble common settings for connecting to
Kafka and add them to the handler class (for example, to KafkaMessageProcessor) by **kwargs_ .

### EXAMPLE:

```commandline

from resistant_kafka.consumer_schemas import ConsumerConfig

process_task_1 = KafkaMessage1Processor(
    config=ConsumerConfig(
        topic_to_subscribe='KafkaTesterProducer1',
        processor_name='KafkaProcessor1',
        bootstrap_servers='localhost:9093',
        group_id='LocalTester1',
        auto_offset_reset='latest',
        enable_auto_commit=False,
)

process_task_2 = KafkaMessage2Processor(
    config=ConsumerConfig(
        topic_to_subscribe='KafkaTesterProducer2',
        processor_name='KafkaProcessor2',
        bootstrap_servers='localhost:9093',
        group_id='LocalTester1',
        auto_offset_reset='latest',
        enable_auto_commit=False,
)

```

##

## Second Step. Add processor

Processor is a class-handler of a specific topic. It allows to perform CRUD operations on received messages from a given
topic **_independently of other processors._**

⚠️ **The name of the main method _"process"_ is reserved and is required for installation**.⚠️

⚠️**Attribute _"message"_ in main method _"process"_** **is required** ⚠️

⚠️**The decorator "_kafka_processor_" is also required** ⚠️, which is responsible for the operation of the message
stream and the
stable operation of the main method "process". It has the attribute raise_error, which allows to raise an error, while
the work of a specific handler will be stopped.

### EXAMPLE:

```commandline

from resistant_kafka.consumer import ConsumerInitializer, kafka_processor
from resistant_kafka_avataa.message_desirializers import MessageDeserializer

class KafkaMessage1Processor(ConsumerInitializer):
    def __init__(
            self,
            config: ConsumerConfig,
            deserializers: MessageDeserializer = None
    ):
        super().__init__(config=config, deserializers=deserializers)
        self._config = config
        self._deserializers = deserializers

    # required decorator
    # to raise error, instead logging @kafka_processor(raise_error=True)
    @kafka_processor()
    async def process(self, message):
        message_key = message.key().decode("utf-8")
        message_value = message.value().decode("utf-8")

        if message_value in ['WRONG_VALUE']:
            raise ValueError('You catch wrong value')
        
        # here your message proccessing

```

##

## Third Step. Initialization

In order to start topic processors, you should use the "**_init_kafka_connection_**" method, to which you need to pass a
list of
instances of the processor-classes.

### EXAMPLE:

```commandline
from resistant_kafka.consumer import init_kafka_connection

process_task_1 = KafkaMessageProcessor1(
    config=ConsumerConfig(
        topic_to_subscribe='TOPIC_NAME_1',
        processor_name='KafkaMessageProcessor1',
        **consumer_config
    )
)

process_task_2 = KafkaMessageProcessor2(
    config=ConsumerConfig(
        topic_to_subscribe='TOPIC_NAME_2',
        processor_name='KafkaMessageProcessor2',
        **consumer_config
    )
)

init_kafka_connection(
    tasks=[process_task_1, process_task_2]
)
```

###

️⚠️In the way, where you have already created loop - use method **_"process_kafka_connection"_** ⚠️

**_process_kafka_connection_** is a long-running coroutine. Keep a reference to the task,
otherwise it may be garbage collected while it runs.

The coroutine logs any exception before re-raising it, so a failure is never silent even
if nobody reads the task's result — **you do not need a callback just to see the error**.
Add one only when the service has to *react* to a consumer that stopped: fail a readiness
probe, shut down, page someone. Do not log the exception again there — it is already in
the log with its traceback, and a second record only doubles the noise.

```commandline
import asyncio

from resistant_kafka_avataa.consumer import process_kafka_connection


def on_kafka_task_done(task: asyncio.Task) -> None:
    if task.cancelled() or task.exception() is None:
        return
    # Already logged by the library — react, do not re-log.
    app.state.kafka_consumer_healthy = False


kafka_task = asyncio.create_task(
    process_kafka_connection([inventory_changes_processor])
)
kafka_task.add_done_callback(on_kafka_task_done)
```

On shutdown, do not assume the task is still alive: if it has already failed, `cancel()`
does nothing and `await` re-raises its exception, which `suppress(asyncio.CancelledError)`
does not catch.

```commandline
if kafka_task is not None and not kafka_task.done():
    kafka_task.cancel()
with suppress(asyncio.CancelledError, Exception):
    await kafka_task
```

### What happens when the topic does not exist

Before subscribing, every processor checks that its topic is present on the cluster. A
missing topic is **a warning, not a startup failure**: the topic may be created later by
a producer or an administrator, and the subscription starts reading as soon as it
appears. The same applies when cluster metadata cannot be fetched at all — the consumer
subscribes anyway and librdkafka keeps reconnecting.

```text
WARNING - resistant_kafka_avataa.consumer - DocumentsChangesProcessor: topic
'documents.changes' does not exist on localhost:9092. The consumer stays subscribed
and starts reading as soon as the topic appears; until then it consumes nothing.
Check the topic name if this is unexpected.
```

The positive signal to look for is the subscription line, logged once partitions are
assigned. If it never appears, the processor is not reading anything:

```text
INFO - resistant_kafka_avataa.consumer - DocumentsChangesProcessor successfully
subscribed to the topic documents.changes
```

Consumers are started concurrently, and one that fails to start is logged and skipped
without holding back the others. If none of them can start,
**_process_kafka_connection_** raises `KafkaConnectionError`.

However the connection ends — an error in one of the processors, or the `cancel()` your
service sends on shutdown — the remaining processors are stopped and every consumer is
closed, so no client keeps its threads and sockets after the task is gone. Cancelling the
task is therefore a clean shutdown and is not reported as an error.

###

## Additional Step. Add security

To add security, you should set attribute **_security_config_** using class KafkaSecurityConfig

```commandline
from resistant_kafka.common_schemas import KafkaSecurityConfig
from resistant_kafka.consumer_schemas import ConsumerConfig

security_config = KafkaSecurityConfig(
    oauth_cb=method_to_get_token,
    security_protocol='SASL_PLAINTEXT',
    sasl_mechanisms='OAUTHBEARER'
)

consumer_config = ConsumerConfig(
        bootstrap_servers='HOST:PORT',
        group_id='CONSUMER_NAME',
        auto_offset_reset='latest',
        enable_auto_commit=False,
        
        security_config=consumer_config
)
```

For mTLS/SSL connections, set optional certificate paths on `KafkaSecurityConfig`:

```commandline
security_config = KafkaSecurityConfig(
    security_protocol='SSL',
    sasl_mechanisms='',
    ssl_ca_location='/path/to/ca.pem',
    ssl_certificate_location='/path/to/client.crt',
    ssl_key_location='/path/to/client.key',
    ssl_key_password='optional-key-password',
)
```

For `SASL_SSL`, combine SASL settings with the SSL fields above.
##

## Additional Step. Add deserializers


In Kafka, messages are stored as bytes, so we need to get them in the format we expect.
The library provides the ability to _**convert messages from bytes to objects using your 
.proto files**_ or, if no .proto files are available, _**we will convert them to strings for 
your future processing of this data**_.
##
### _PROTO FILES_
In case you have proto files that can help you format your messages - we can 
convert them from bytes to protobuf structure.

This can be done with Kafka Schema Registry, if your project doesn't have Kafka Schema Registry -
we will convert bytes to strings.

You should use **_MessageDeserializer_** to registry your proto files with which you expect messages from the topic
####

#### _REGISTRY .proto FILES_

```commandline
from resistant_kafka_avataa.message_desirializers import MessageDeserializer

deserializers_producer = MessageDeserializer(
    schema_registry_url="https://localhost:8081",
    topic='KafkaTesterProducer1'
)
deserializers_producer.register_protobuf_deserializer(ProtoFileWithData_1)
deserializers_producer.register_protobuf_deserializer(ProtoFileWithData_2)


process_task_1 = KafkaMessage1Processor(
    config=ConsumerConfig(
        topic_to_subscribe='KafkaTesterProducer1',
        processor_name='KafkaProcessor1',
        **consumer_config
    ),
    deserializers=deserializers_producer_1
)
```
###
### _SIMPLE MESSAGES_
```commandline
from resistant_kafka_avataa.message_desirializers import MessageDeserializer

deserializers_producer_2 = MessageDeserializer(
    topic='KafkaTesterProducer2'
)
```

###
### _READ DESERIALIZED MESSAGES_
Using the **_deserialize_** method you can convert the byte format of the message value
from the format of objects described in .proto and end up with an object instead of bytes
```commandline
class KafkaMessage1Processor(ConsumerInitializer):
    def __init__(
            self,
            config: ConsumerConfig,
            deserializers: MessageDeserializer = None
    ):
        super().__init__(config=config, deserializers=deserializers)
        self._config = config
        self._deserializers = deserializers

    @kafka_processor(store_error_messages=True)
    async def process(self, message):
        message_key = message.key().decode("utf-8")
        message_value = message.value().decode("utf-8")

        if message_value in ['WRONG_VALUE']:
            raise ValueError('You catch wrong value')
        
        deserialized_message = self._deserializers.deserialize(message=message)
```

###

## Additional Step. Integrate Redis

```bash
    pip install redis=4.5.4
```

```commandline
from resistant_kafka_avataa.common_schemas import RedisStoreConfig

redis_store_config = RedisStoreConfig(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True,
)

process_task = KafkaMessageProcessor(
    config=ConsumerConfig(
        topic_to_subscribe='KafkaTesterProducer1',
        processor_name='KafkaProcessor1',
        bootstrap_servers='localhost:9093',
        group_id='LocalTester1',
        auto_offset_reset='latest',
        enable_auto_commit=False,

        redis_store_config=redis_store_config,
    )
)

class KafkaMessageProcessor(ConsumerInitializer):
    def __init__(
            self,
            config: ConsumerConfig
    ):
        super().__init__(config=config)
        self._config = config
    
    # IF "TRUE", ERROR MESSAGES DATA ARE STORED IN REDIS
    @kafka_processor(store_error_messages=True)
    async def process(self, message):
        
        # HERE YOU PROCESS KAFKA MESSAGES
        pass
```

##

# Producer Initializer

## First Step. Add enviroment variables

To configure a producer you will need only 2 fields: URL for connecting Kafka and the producer name.

```commandline
producer_config = ProducerConfig(
        producer_name='KafkaTesterProducer1',
        bootstrap_servers='HOST:PORT',
)
```

##

## Second Step. Add processor

The  **_send_message_** method of **_ProducerInitializer_** class allows to send a message to a topic

Also an optional parameter of **_DataSend_** scheme is **_"headers"_** which allows to send additional information in a
message without changing the structure of this message.

### EXAMPLE:

```commandline
task = ProducerInitializer(
    config=producer_config
)

task.send_message(
    data_to_send=DataSend(
        key='KEY1',
        value='VALUE1',
    )
)

# with headers
task.send_message(
    data_to_send=DataSend(
        key='KEY2',
        value='VALUE12,
        headers=[('additinal_key', 'additinal_value')]
    )
)
```

##

## Additional Step. Add security

To add security, you should set attribute **_security_config_** using class KafkaSecurityConfig

```commandline
from resistant_kafka import ProducerConfig
from resistant_kafka.common_schemas import KafkaSecurityConfig

security_config = KafkaSecurityConfig(
    oauth_cb=method_to_get_token,
    security_protocol='SASL_PLAINTEXT',
    sasl_mechanisms='OAUTHBEARER'
)

producer_config = ProducerConfig(
        producer_name='KafkaTesterProducer1',
        bootstrap_servers='HOST:PORT',

        security_config=consumer_config
)
```

SSL/mTLS certificate paths can be set on `KafkaSecurityConfig` (see consumer security section above).
#


## Additional Step. Add serializers


In Kafka, messages are stored as bytes, so we need to get them in the format we expect.
The library provides the ability to _**convert messages from bytes to objects using your 
.proto files**_ or, if no .proto files are available, _**we will convert them to strings for 
your future processing of this data**_.
##
### _PROTO FILES_
In case you have proto files that can help you format your messages - we can 
convert them from bytes to protobuf structure.

This can be done with Kafka Schema Registry, if your project doesn't have Kafka Schema Registry -
we will convert bytes to strings.

You should use **_MessageSerializer_** to registry your proto files with which you expect messages from the topic
####

#### _REGISTRY .proto FILES_

```commandline
from resistant_kafka_avataa.message_serializers import MessageSerializer

serializer_task = MessageSerializer(
    schema_registry_url="https://localhost:8081",
    topic='KafkaTesterProducer1'
)
serializer_task.register_protobuf_deserializer(ProtoFile1)
serializer_task.register_protobuf_deserializer(ProtoFile2)

_producer_manager.send_message(
    data_to_send=DataSend(
        key=key,
        value=serializer_task.serialize(
            message_to_send=message_to_send,
            class_name=ProtoFile1
        ),
    ),
)
```
###
### _SIMPLE MESSAGES_
```commandline
from resistant_kafka_avataa.message_serializers import MessageSerializer

serializer_task = MessageSerializer(
    topic='KafkaTesterProducer1'
)
_producer_manager.send_message(
    data_to_send=DataSend(
        key=key,
        value=serializer_task.serialize(
            message_to_send=message_to_send
        ),
    ),
)
```

## Installation

```bash
    pip install resistant-kafka-avataa
```

# CONSUMER CODE EXAMPLE

```commandline

from custom_utils import custom_token_method
from resistant_kafka.common_schemas import KafkaSecurityConfig
from resistant_kafka.consumer_schemas import ConsumerConfig
from resistant_kafka.consumer import ConsumerInitializer, kafka_processor, init_kafka_connection

consumer_config = KafkaSecurityConfig(
    oauth_cb=custom_token_method,
    security_protocol='SASL_PLAINTEXT',
    sasl_mechanisms='OAUTHBEARER'
)


class KafkaMessage1Processor(ConsumerInitializer):
    def __init__(
            self,
            config: ConsumerConfig,
            deserializers: MessageDeserializer = None
    ):
        super().__init__(config=config, deserializers=deserializers)
        self._config = config
        self._deserializers = deserializers

    @kafka_processor(store_error_messages=True)
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
            config: ConsumerConfig,
            deserializers: MessageDeserializer = None
    ):
        super().__init__(config=config, deserializers=deserializers)
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


deserializers_producer_1 = MessageDeserializer(
    schema_registry_url='http://localhost:8081',
    topic='KafkaTesterProducer1'
)
deserializers_producer_1.register_protobuf_deserializer(ProtoFileToDeserialize)

deserializers_producer_2 = MessageDeserializer(
    topic='KafkaTesterProducer2'
)

process_task_1 = KafkaMessage1Processor(
    config=ConsumerConfig(
        topic_to_subscribe='KafkaTesterProducer1',
        processor_name='KafkaProcessor1',
        bootstrap_servers='localhost:9093',
        group_id='LocalTester1',
        auto_offset_reset='latest',
        enable_auto_commit=False,
        redis_store_config=redis_store_config,
        security_config=consumer_config
    ),
    deserializers=deserializers_producer_1
)

process_task_2 = KafkaMessage2Processor(
    config=ConsumerConfig(
        topic_to_subscribe='KafkaTesterProducer2',
        processor_name='KafkaProcessor2',
        bootstrap_servers='localhost:9093',
        group_id='LocalTester1',
        auto_offset_reset='latest',
        enable_auto_commit=False,
        redis_store_config=redis_store_config,
        security_config=consumer_config
    ),
    deserializers=deserializers_producer_2
)

init_kafka_connection(
    tasks=[process_task_1, process_task_2]
)
```

#

# PRODUCER CODE EXAMPLE

```commandline
from custom_utils import custom_token_method
from resistant_kafka import ProducerInitializer, ProducerConfig, DataSend
from resistant_kafka.common_schemas import KafkaSecurityConfig

security_config = KafkaSecurityConfig(
    oauth_cb=custom_token_method,
    security_protocol='SASL_PLAINTEXT',
    sasl_mechanisms='OAUTHBEARER'
)

task = ProducerInitializer(
    config=ProducerConfig(
        producer_name='KafkaTesterProducer1',
        bootstrap_servers='HOST:PORT',
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
        bootstrap_servers='HOST:PORT',
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

```