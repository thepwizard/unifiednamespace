"""
Type of data to be retrieved from the UNS
Maps to MQTT messages to the UNS
"""
import json
import logging
import typing

import strawberry
from strawberry.types import Info
from uns_mqtt.mqtt_listener import UnsMQTTClient

from uns_graphql.type.basetype import BytesPayload, JSONPayload

LOGGER = logging.getLogger(__name__)


@strawberry.type(description="MQTT message which published in the UNS platform")
class MQTTMessage:
    """
    Model of a UNS Events
    """

    # Fully qualified path of the namespace including current name
    # Maps to the topic where the payload was  published e.g. ent1/fac1/area5
    topic: str = strawberry.field(description="Fully qualified path of the namespace. i.e. the MQTT Topic")

    # stores the raw data of the event
    _raw_payload: strawberry.Private[bytes]

    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self._raw_payload = payload

    # # The payload which was published was either a JSON, a string or bytes

    @strawberry.field(name="payload", description="the payload of the MQTT message\n -JSON for UNS \n -bytes for sparkplugB")
    def resolve_payload(
        self,
        info: Info,  # noqa: ARG002
    ) -> typing.Optional[typing.Union[JSONPayload, BytesPayload]]:
        if UnsMQTTClient.is_topic_matched(UnsMQTTClient.SPB_STATE_MSG_TYPE, self.topic):
            # Message to sparkplug STATE message
            return JSONPayload(data=self._raw_payload.decode("utf-8"))

        elif self.topic.startswith(UnsMQTTClient.SPARKPLUG_NS):
            # Message to sparkplug name space in protobuf i.e. BytesPayload
            return BytesPayload(data=self._raw_payload)

        else:
            # Message to UNS or spb STATE message f i.e. JSONPayload
            try:
                return JSONPayload(data=self._raw_payload.decode("utf-8"))
            except json.JSONDecodeError as ex:
                LOGGER.error(f"Expected JSON String in payload:{self._raw_payload}")
                raise ex
