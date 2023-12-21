import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import strawberry
import strawberry.tools
from uns_graphql.backend.historian import HistorianDBPool
from uns_graphql.input.mqtt import MQTTTopic, MQTTTopicInput
from uns_graphql.queries.historic_events import Query as HistorianQuery
from uns_graphql.type.basetype import JSONPayload
from uns_graphql.type.historical_event import HistoricalUNSEvent

# model for db entry - time, topic, publisher, payload
DatabaseRow = tuple[datetime, str, str, dict]
# mock data
test_data_set: list[DatabaseRow] = [
    (datetime(2023, 11, 29, 4, 26, 40, tzinfo=UTC), "a/b/c", "client4", json.dumps({"key1": "value1"})),
    (datetime(2023, 11, 29, 4, 43, 20, tzinfo=UTC), "a/b/c", "client5", json.dumps({"key2": "value2"})),
    (datetime(2023, 11, 29, 4, 51, 40, tzinfo=UTC), "a/b/c", "client6", json.dumps({"key3": "value3"})),
    (datetime(2023, 11, 29, 5, 0, tzinfo=UTC), "topic1", "client1", json.dumps({"key4": "value4"})),
    (datetime(2023, 11, 29, 8, 3, 20, tzinfo=UTC), "topic1/subtopic1", "client1", json.dumps({"key5": "value5.1"})),
    (datetime(2023, 11, 29, 8, 3, 20, tzinfo=UTC), "topic1/subtopic2", "client2", json.dumps({"key5": "value5.2"})),
    (datetime(2023, 11, 29, 11, 23, 20, tzinfo=UTC), "topic3", "client1", json.dumps({"key6": "value6"})),
    (
        datetime.fromtimestamp(170129000, UTC),
        "test/nested/json",
        "nested",
        json.dumps({"a": "value1", "b": [10, 23, 23, 34], "c": {"k1": "v1", "k2": 100}, "k3": "outer_v1"}),
    ),
]
# Mock the datahandler
mocked_db_pool = MagicMock(spec=HistorianDBPool, autospec=True)

# mocked_db_pool.__aiter__.return_value = mocked_db_pool
mocked_db_pool.__aenter__.return_value = mocked_db_pool
# Mocking all the query functions to give the same result
mocked_db_pool.get_historic_events.return_value = [
    HistoricalUNSEvent(timestamp=x[0], topic=x[1], publisher=x[2], payload=JSONPayload(data=x[3])) for x in test_data_set
]
mocked_db_pool.get_historic_events_for_property_keys.return_value = [
    HistoricalUNSEvent(timestamp=x[0], topic=x[1], publisher=x[2], payload=JSONPayload(data=x[3])) for x in test_data_set
]
mocked_db_pool.execute_prepared.return_value = [
    HistoricalUNSEvent(timestamp=x[0], topic=x[1], publisher=x[2], payload=JSONPayload(data=x[3])) for x in test_data_set
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "topics, from_date, to_date, has_result_errors",
    [
        (["topic1/#"], datetime(2023, 11, 29, 4, 43, 20), datetime(2023, 11, 29, 11, 56, 40), False),
        (["topic1/+"], datetime(2023, 11, 29, 4, 43, 20), datetime(2023, 11, 29, 11, 56, 40), False),
        (["#"], None, datetime(2023, 11, 29, 11, 23, 20), False),
        (["#"], datetime(2023, 11, 29, 11, 23, 20), None, False),
        (["topic1/#", "topic3"], datetime(2023, 11, 29, 4, 43, 20), datetime(2023, 11, 29, 11, 56, 40), False),
        (["+"], None, None, False),
    ],
)
async def test_get_historic_events_in_time_range_mock(
    topics: list[str],
    from_date: datetime,
    to_date: datetime,
    has_result_errors: bool,
):
    mqtt_topic_list = [MQTTTopicInput.from_pydantic(MQTTTopic(topic=topic)) for topic in topics]
    with patch("uns_graphql.queries.historic_events.HistorianDBPool", return_value=mocked_db_pool):
        historian_query = HistorianQuery()
        try:
            result = await historian_query.get_historic_events_in_time_range(mqtt_topic_list, from_date, to_date)
        except Exception:
            assert has_result_errors, "Should not throw any exceptions"
        assert result is not None  # test was successful


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "topics, from_date, to_date, has_result_errors",
    [
        (["topic1/#"], "2023-11-29 04:43:20", "2023-11-29 11:56:40", False),
        (["topic1/+"], "2023-11-29 04:43:20", "2023-11-29 11:56:40", False),
        (["#"], None, "2023-11-29 11:23:20", False),
        (["#"], "2023-11-29 11:23:20", None, False),
        (["topic1/#", "topic3"], "2023-11-29 04:43:20", "2023-11-29 11:56:40", False),
        ([], None, None, False),
    ],
)
async def test_strawberry_get_historic_events_in_time_range_mock(
    topics: list[str],
    from_date: str,
    to_date: str,
    has_result_errors: bool,
):
    #   getHistoricEventsInTimeRange(
    #     topics: [{", ".join([f'{{ topic: "{topic}" }}' for topic in topics])}]"""

    query: str = """query TestQuery($mqtt_topics:[MQTTTopicInput!]!, $from_date:DateTime, $to_date:DateTime ) {
                  getHistoricEventsInTimeRange(
                    topics: $mqtt_topics
                    fromDatetime: $from_date
                    toDatetime: $to_date
                  ){
                    timestamp
                    topic
                    publisher
                    payload {
                        data
                    }
                  }
            }
    """

    mqtt_topics: list[dict[str, str]] = [{"topic": x} for x in topics]
    schema = strawberry.Schema(query=HistorianQuery)

    with patch("uns_graphql.queries.historic_events.HistorianDBPool", return_value=mocked_db_pool):
        result = await schema.execute(
            query=query, variable_values={"mqtt_topics": mqtt_topics, "from_date": from_date, "to_date": to_date}
        )
        if not has_result_errors:
            assert not result.errors


# def test_strawberry_get_historic_events_for_property_keys(query: str):

# def test_strawberry_get_events_by_publishers
