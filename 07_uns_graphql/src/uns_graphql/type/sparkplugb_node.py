import logging
import typing
from datetime import UTC, datetime

import strawberry
from uns_sparkplugb.generated.sparkplug_b_pb2 import Payload
from uns_sparkplugb.uns_spb_enums import SPBParameterTypes
from uns_sparkplugb.uns_spb_helper import SPBDataSetDataTypes, SPBMetricDataTypes, SPBPropertyValueTypes

from uns_graphql.type.basetype import BytesPayload

LOGGER = logging.getLogger(__name__)


@strawberry.type
class SPBMetadata:
    """
    Model of Metadata in SPBv1.0 payload
    """

    is_multi_part: typing.Optional[bool]
    content_type: typing.Optional[str]
    size: typing.Optional[int]
    seq: typing.Optional[int]
    file_name: typing.Optional[str]
    file_type: typing.Optional[str]
    md5: typing.Optional[str]
    description: typing.Optional[str]

    def __init__(self, metadata: Payload.MetaData):
        self.is_multi_part = metadata.is_multi_part if metadata.HasField("is_multi_part") else None
        self.content_type = metadata.content_type if metadata.HasField("content_type") else None
        self.size = metadata.size if metadata.HasField("size") else None
        self.seq = metadata.seq if metadata.HasField("seq") else None
        self.file_name = metadata.file_name if metadata.HasField("file_name") else None
        self.file_type = metadata.file_type if metadata.HasField("file_type") else None
        self.md5 = metadata.md5 if metadata.HasField("md5") else None
        self.description = metadata.description if metadata.HasField("description") else None


class SPBPropertySet:
    """
    Model of PropertySet in SPBv1.0 payload
    """

    keys: list[str]
    values: list[typing.Annotated["SPBPropertyValue", strawberry.lazy(".")]]

    def __init__(self, propertyset: Payload.PropertySet) -> None:
        self.keys = propertyset.keys
        self.values = [SPBPropertyValue(value) for value in propertyset.values]


class SPBPropertyValue:
    """
    Model of PropertyValue in SPBv1.0 payload
    """

    is_null: typing.Optional[bool]
    datatype: str
    value: [
        int,
        float,
        str,
        typing.Annotated["SPBPropertySet", strawberry.lazy(".")],
        list[typing.Annotated["SPBPropertySet", strawberry.lazy(".")]],
    ]

    def __init__(self, property_value: Payload.PropertyValue):
        self.is_null = property_value.is_null if property_value.HasField("is_null") else None
        self.datatype = SPBPropertyValueTypes(property_value.type).name
        if self.is_null:
            self.value = None
        else:
            match property_value.type:
                case SPBPropertyValueTypes.PropertySet:
                    self.value = SPBPropertySet(
                        propertyset=SPBPropertyValueTypes.PropertySet.get_value_from_sparkplug(property_value)
                    )

                case SPBPropertyValueTypes.PropertySetList:
                    self.value = [
                        SPBPropertySet(propertyset)
                        for propertyset in SPBPropertySet(
                            SPBPropertyValueTypes.PropertySetList.get_value_from_sparkplug(property_value)
                        )
                    ]
                case _:
                    self.value = SPBPropertyValueTypes(property_value.type).get_value_from_sparkplug(property_value)


@strawberry.type
class SPBDataSetValue:
    """
    Model of DataSet->Row->Value in SPBv1.0 payload
    """

    datatype: strawberry.Private[SPBDataSetDataTypes]
    value: typing.Union[int, float, bool, str]

    def __init__(self, datatype: int, dataset_value: Payload.DataSet.DataSetValue):
        self.datatype = SPBDataSetDataTypes(datatype)
        self.value = self.datatype.get_value_from_sparkplug(dataset_value)


@strawberry.type
class SPBDataSetRow:
    """
    Model of DataSet->Row in SPBv1.0 payload
    """

    elements: list[SPBDataSetValue]

    def __init__(self, datatypes: list[int], row: Payload.DataSet.Row):
        self.elements = [
            SPBDataSetValue(datatype=datatype, dataset_value=dataset_value)
            for datatype, dataset_value in zip(datatypes, row.elements)
        ]


@strawberry.type
class SPBDataSet:
    """
    Model of DataSet in SPBv1.0 payload
    """

    num_of_columns: int
    columns: list[str]
    # maps to spb data types
    types: list[str]
    rows: list[SPBDataSetRow]

    def __init__(self, dataset: Payload.DataSet):
        self.types = [SPBDataSetDataTypes(datatype).name for datatype in dataset.types]
        self.num_of_columns = dataset.num_of_columns
        self.columns = dataset.columns
        self.rows = [SPBDataSetRow(datatypes=dataset.types, row=row) for row in dataset.rows]


class SPBTemplateParameter:
    """
    Model of a SPB Template Parameter,
    """

    name: str
    datatype: str
    value: any

    def __init__(self, parameter: Payload.Template.Parameter) -> None:
        self.name = parameter.name
        self.datatype = SPBParameterTypes(parameter.type).name
        self.value = SPBParameterTypes(parameter.type).get_value_from_sparkplug(parameter)


class SPBTemplate:
    """
    Model of Template in SPBv1.0 payload
    """

    version: typing.Optional[str]
    metrics: list[typing.Annotated["SPBMetric", strawberry.lazy(".")]]
    parameters: typing.Optional[list[SPBTemplateParameter]]
    template_ref: typing.Optional[str]
    is_definition: typing.Optional[bool]

    def __init__(self, template: Payload.Template):
        self.version = template.version if template.HasField("version") else None
        self.metrics = [SPBMetric(metric) for metric in template.metrics]
        self.template_ref = template.template_ref if template.HasField("template_ref") else None
        self.is_definition = template.is_definition if template.HasField("is_definition") else None
        self.parameters = [SPBTemplateParameter(parameter) for parameter in template.parameters]


@strawberry.type
class SPBMetric:
    """
    Model of a SPB Metric, which is within a SPBNode
    """

    name: str
    alias: typing.Optional[int]
    timestamp: datetime
    datatype: str
    is_historical: typing.Optional[bool]
    is_transient: typing.Optional[bool]
    is_null: typing.Optional[bool]
    metadata: typing.Optional[SPBMetadata]
    properties: typing.Optional[SPBPropertySet]
    value: typing.Union[
        int,
        float,
        bool,
        str,
        strawberry.ID,
        BytesPayload,
        typing.Annotated["SPBDataSet", strawberry.lazy(".")],
        typing.Annotated["SPBTemplate", strawberry.lazy(".")],
    ]

    def __init__(self, metric: Payload.Metric):
        self.name = metric.name
        self.alias = metric.alias if metric.HasField("alias") else None
        self.timestamp = metric.timestamp
        self.datatype = SPBMetricDataTypes(metric.datatype).name
        self.is_historical = metric.is_historical if metric.HasField("is_historical") else None
        self.is_transient = metric.is_transient if metric.HasField("is_transient") else None
        self.is_null = metric.is_null if metric.HasField("is_null") else None
        self.metadata = SPBMetadata(metric.metadata) if metric.HasField("metadata") else None
        self.properties = SPBPropertySet(metric.properties) if metric.HasField("properties") else None

        if self.is_null:
            self.value = None
        else:
            match metric.datatype:
                case SPBMetricDataTypes.Bytes | SPBMetricDataTypes.File:
                    self.value = BytesPayload(data=SPBMetricDataTypes(metric.datatype).get_value_from_sparkplug(metric))

                case SPBMetricDataTypes.DataSet:
                    self.value = SPBDataSet(SPBMetricDataTypes.DataSet.get_value_from_sparkplug(metric))

                case SPBMetricDataTypes.Template:
                    self.value = SPBTemplate(SPBMetricDataTypes.Template.get_value_from_sparkplug(metric))

                case _:
                    self.value = SPBMetricDataTypes(metric.datatype).get_value_from_sparkplug(metric)


@strawberry.type
class SPBNode:
    """
    Model of a SPB Node representing the Payload Object
    """

    # Fully qualified path of the namespace including current name
    # Usually maps to the topic where the messages were published
    # e.g. spBv1.0/[GROUP]/[MESSAGE_TYPE]/[EDGE_NODE]/[DEVICE]
    topic: str

    # Merged Composite of all Metric published to this node

    # Timestamp of when this node was last modified in milliseconds
    timestamp: datetime

    # Metrics published to the spBv1.0 namespace using protobuf payloads
    metrics: list[SPBMetric]

    # sequence
    seq: int

    # UUID for this message
    uuid: typing.Optional[strawberry.ID]

    # array of bytes used for any custom binary encoded data.
    body: typing.Optional[strawberry.scalars.Base64]

    def __init__(self, topic: str, payload: Payload | bytes | dict):
        self.topic = topic

        if isinstance(payload, bytes):
            parsed_payload = Payload()
            parsed_payload.ParseFromString(payload)
            payload = parsed_payload
        # Timestamp is normally in milliseconds and needs to be converted to microsecond
        # All payloads have a timestamp
        self.timestamp = datetime.fromtimestamp(payload.timestamp / 1000, UTC)
        # Set other fields only if they were initialized in the payload
        self.seq = payload.seq if payload.HasField("seq") else None
        self.uuid = strawberry.ID(payload.uuid) if payload.HasField("uuid") else None
        self.body = strawberry.scalars.Base64(payload.body) if payload.HasField("body") else None
        # The HasField method does not work for repeated fields
        self.metrics = [SPBMetric(metric) for metric in payload.metrics]
