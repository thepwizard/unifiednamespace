"""
MQTT listener that listens to SparkplugB name space for messages and publishes to ISA-95 UNS
"""
import inspect
import logging
import os
import random
import sys
import time

from uns_spb_mapper.sparkplugb_enc_config import settings

# From http://stackoverflow.com/questions/279237/python-import-a-module-from-a-folder
cmd_subfolder = os.path.realpath(
    os.path.abspath(
        os.path.join(
            os.path.split(inspect.getfile(inspect.currentframe()))[0], '..',
            '..', '..', '02_mqtt-cluster', 'src')))
if cmd_subfolder not in sys.path:
    sys.path.insert(0, cmd_subfolder)
    sys.path.insert(
        0,
        os.path.abspath(
            os.path.join(cmd_subfolder, "..", "..", "05_sparkplugb", "src")))

from uns_spb_mapper.spb2unspublisher import Spb2UNSPublisher
from uns_mqtt.mqtt_listener import UnsMQTTClient

LOGGER = logging.getLogger(__name__)


# listens to SparkplugB name space for messages and publishes to ISA-95
# https://www.hivemq.com/solutions/manufacturing/smart-manufacturing-using-isa95-mqtt-sparkplug-and-uns/
class UNSSparkPlugBMapper:
    """
    MQTT listener that listens to SparkplugB name space for messages and publishes to ISA-95 UNS
    """

    def __init__(self):
        self.uns_client: UnsMQTTClient = None
        self.load_mqtt_configs()
        self.load_sparkplugb_configs()
        self.uns_client: UnsMQTTClient = UnsMQTTClient(
            client_id=self.client_id,
            clean_session=self.clean_session,
            userdata=None,
            protocol=self.mqtt_mqtt_version_code,
            transport=self.mqtt_transport,
            reconnect_on_failure=self.reconnect_on_failure)

        self.uns_client.on_message = self.on_message
        self.uns_client.on_disconnect = self.on_disconnect

        self.spb_2_uns_pub: Spb2UNSPublisher = Spb2UNSPublisher(
            self.uns_client)
        self.uns_client.run(host=self.mqtt_host,
                            port=self.mqtt_port,
                            username=self.mqtt_username,
                            password=self.mqtt_password,
                            tls=self.mqtt_tls,
                            keepalive=self.mqtt_keepalive,
                            topics=self.topics,
                            qos=self.mqtt_qos)

    def load_mqtt_configs(self):
        """
        Read the MQTT configurations required to connect to the MQTT broker
        """
        # generate client ID with pub prefix randomly
        self.client_id = f'uns_sparkplugb_listener-{time.time()}-{random.randint(0, 1000)}'

        self.mqtt_transport: str = settings.get("mqtt.transport", "tcp")
        self.mqtt_mqtt_version_code: int = settings.get(
            "mqtt.version", UnsMQTTClient.MQTTv5)
        self.mqtt_qos: int = settings.get("mqtt.qos", 2)
        self.reconnect_on_failure: bool = settings.get(
            "mqtt.reconnect_on_failure", True)
        self.clean_session: bool = settings.get("mqtt.clean_session", None)

        self.mqtt_host: str = settings.mqtt["host"]
        self.mqtt_port: int = settings.get("mqtt.port", 1883)
        self.mqtt_username: str = settings.mqtt["username"]
        self.mqtt_password: str = settings.mqtt["password"]
        self.mqtt_tls: dict = settings.get("mqtt.tls", None)
        self.topics: list = settings.get("mqtt.topics", ["spBv1.0/#"])
        self.mqtt_keepalive: int = settings.get("mqtt.keep_alive", 60)
        self.mqtt_ignored_attributes: dict = settings.get(
            "mqtt.ignored_attributes", None)
        self.mqtt_timestamp_key = settings.get("mqtt.timestamp_attribute",
                                               "timestamp")
        if self.mqtt_host is None:
            raise ValueError(
                "MQTT Host not provided. Update key 'mqtt.host' in '../../conf/settings.yaml'"
            )

    def load_sparkplugb_configs(self):
        """
        Load the SparkplugB configurations
        """
        # Currently no configurations

    def on_message(self, client, userdata, msg):
        """
        Callback function executed every time a message is received by the subscriber
        """
        LOGGER.debug("{"
                     "Client: %s,"
                     "Userdata: %s,"
                     "Message: %s,"
                     "}", str(client), str(userdata), str(msg))
        try:
            topic_path: list[str] = msg.topic.split('/')
            # sPB topic structure spBv1.0/<group_id>/<message_type>/<edge_node_id>/<[device_id]>
            # device_id is optional. all others are mandatory
            if len(topic_path) >= 4:
                group_id = topic_path[1]
                message_type = topic_path[2]
                edge_node_id = topic_path[3]
                device_id = None
                if len(topic_path) == 5:
                    device_id = topic_path[4]
                else:
                    raise ValueError(
                        f"Unknown SparkplugB topic received: {msg.topic}." +
                        f"Depth of tree should not be more than 5, got {len(topic_path)}"
                    )
                self.spb_2_uns_pub.transform_spb_and_publish_to_uns(
                    msg.payload, group_id, message_type, edge_node_id,
                    device_id)
            else:
                raise ValueError(
                    f"Unknown SparkplugB topic received: {msg.topic}")

        except Exception as ex:
            LOGGER.error("Error parsing SparkplugB message payload: %s",
                         str(ex),
                         stack_info=True,
                         exc_info=True)
            raise ex

    def on_disconnect(self, client, userdata, result_code, properties=None):
        """
        Callback function executed every time the client is disconnected from the MQTT broker
        """
        # Cleanup when the MQTT broker gets disconnected
        LOGGER.debug("SparkplugB listener got disconnected")
        if result_code != 0:
            LOGGER.error("Unexpected disconnection.:%s",
                         str(result_code),
                         stack_info=True,
                         exc_info=True)


def main():
    """
    Main function invoked from command line
    """
    try:
        uns_spb_mapper = UNSSparkPlugBMapper()
        uns_spb_mapper.uns_client.loop_forever()
    finally:
        if uns_spb_mapper is not None:
            uns_spb_mapper.uns_client.disconnect()


if __name__ == '__main__':
    main()
