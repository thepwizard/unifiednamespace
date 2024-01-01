"""
MQTT listener that listens to ISA-95 UNS and SparkplugB and persists all messages to the Historian
"""
import asyncio
import logging
import random
import time

from uns_mqtt.mqtt_listener import UnsMQTTClient

from uns_historian.historian_config import MQTTConfig
from uns_historian.historian_handler import HistorianHandler

LOGGER = logging.getLogger(__name__)


class UnsMqttHistorian:
    """
    MQTT listener that listens to ISA-95 UNS and SparkplugB and
    persists all messages to the Historian
    """

    def __init__(self):
        self.client_id = f"historian-{time.time()}-{random.randint(0, 1000)}"  # noqa: S311
        self.uns_client: UnsMQTTClient = UnsMQTTClient(
            client_id=self.client_id,
            clean_session=MQTTConfig.clean_session,
            userdata=None,
            protocol=MQTTConfig.version,
            transport=MQTTConfig.transport,
            reconnect_on_failure=MQTTConfig.reconnect_on_failure,
        )
        # Callback messages
        self.uns_client.on_message = self.on_message
        self.uns_client.on_disconnect = self.on_disconnect
        loop = asyncio.get_event_loop()
        loop.run_until_complete(HistorianHandler.get_shared_pool())
        self.uns_client.run(
            host=MQTTConfig.host,
            port=MQTTConfig.port,
            username=MQTTConfig.username,
            password=MQTTConfig.password,
            tls=MQTTConfig.tls,
            keepalive=MQTTConfig.keepalive,
            topics=MQTTConfig.topics,
            qos=MQTTConfig.qos,
        )

    def on_message(self, client, userdata, msg):
        """
        Callback function executed every time a message is received by the subscriber
        """
        LOGGER.debug("{" "Client: %s," "Userdata: %s," "Message: %s," "}", str(client), str(userdata), str(msg))

        try:
            # get the payload as a dict object
            filtered_message = self.uns_client.get_payload_as_dict(
                topic=msg.topic, payload=msg.payload, mqtt_ignored_attributes=MQTTConfig.ignored_attributes
            )

            # Async Historian persistance method
            async def run_async_handler():
                async with HistorianHandler() as uns_historian_handler:
                    await uns_historian_handler.persist_mqtt_msg(
                        client_id=client._client_id.decode(),
                        topic=msg.topic,
                        timestamp=float(filtered_message.get(MQTTConfig.timestamp_key, time.time())),
                        message=filtered_message,
                    )

            loop = asyncio.get_event_loop()
            loop.run_until_complete(run_async_handler())

        except SystemError as system_error:
            LOGGER.error(
                "Fatal Error while parsing Message: %s\nTopic: %s \nMessage:%s\nExiting.........",
                str(system_error),
                msg.topic,
                msg.payload,
                stack_info=True,
                exc_info=True,
            )
        except Exception as ex:
            LOGGER.error(
                "Error persisting the message to the Historian DB: %s\nTopic: %s \nMessage:%s",
                str(ex),
                msg.topic,
                msg.payload,
                stack_info=True,
                exc_info=True,
            )

    def on_disconnect(
        self,
        client,  # noqa: ARG002
        userdata,  # noqa: ARG002
        result_code,
        properties=None,  # noqa: ARG002
    ) -> None:
        """
        Callback function executed every time the client is disconnected from the MQTT broker
        """
        if result_code != 0:
            LOGGER.error("Unexpected disconnection.:%s", str(result_code), stack_info=True, exc_info=True)
        # dont close the DB Pool as the client may disconnect multiple times and reconnect


def main():
    """
    Main function invoked from command line
    """
    try:
        uns_mqtt_historian = None
        uns_mqtt_historian = UnsMqttHistorian()
        uns_mqtt_historian.uns_client.loop_forever()
    finally:
        if uns_mqtt_historian is not None:
            uns_mqtt_historian.uns_client.disconnect()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(HistorianHandler.close_pool())


if __name__ == "__main__":
    main()
