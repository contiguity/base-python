# ruff: noqa: S101, PLR2004
from collections.abc import Generator
from typing import Any

import pytest
from dotenv import load_dotenv
from typing_extensions import TypedDict

from contiguity_base.base import Base, FetchResponse, ItemConflictError
from tests import random_string

load_dotenv()


class TestItemDict(TypedDict):
    key: str
    field1: str
    field2: str
    field3: int
    field4: int
    field5: list[str]
    field6: list[int]
    field7: dict[str, str]


def create_test_item(key: str = "test_key", /) -> TestItemDict:
    return {
        "key": key,
        "field1": random_string(),
        "field2": random_string(),
        "field3": 1,
        "field4": 0,
        "field5": ["foo", "bar"],
        "field6": [1, 2],
        "field7": {"foo": "bar"},
    }


@pytest.fixture
def base() -> Generator[Base[TestItemDict], Any, None]:
    base = Base("test_base_typeddict", item_type=TestItemDict)
    for item in base.query().items:
        base.delete(item["key"])
    yield base
    for item in base.query().items:
        base.delete(item["key"])


def test_get(base: Base[TestItemDict]) -> None:
    item = create_test_item()
    base.insert(item)
    fetched_item = base.get("test_key")
    assert fetched_item == item


def test_get_nonexistent(base: Base[TestItemDict]) -> None:
    with pytest.warns(DeprecationWarning):
        assert base.get("nonexistent_key") is None


def test_delete(base: Base[TestItemDict]) -> None:
    item = create_test_item()
    base.insert(item)
    base.delete("test_key")
    with pytest.warns(DeprecationWarning):
        assert base.get("test_key") is None


def test_insert(base: Base[TestItemDict]) -> None:
    item = create_test_item()
    inserted_item = base.insert(item)
    assert inserted_item == item


def test_insert_existing(base: Base[TestItemDict]) -> None:
    item = create_test_item()
    base.insert(item)
    with pytest.raises(ItemConflictError):
        base.insert(item)


def test_put(base: Base[TestItemDict]) -> None:
    items = [create_test_item(f"test_key_{i}") for i in range(3)]
    response = base.put(*items)
    assert response == items


def test_update(base: Base[TestItemDict]) -> None:
    item = create_test_item()
    base.insert(item)
    updated_item = base.update(
        {
            "field1": "updated_value",
            # Trim will not pass type validation when using TypedDict
            # because TypedDict does not support default values.
            "field3": base.util.increment(2),
            "field4": base.util.increment(-2),
            "field5": base.util.append("baz"),
            "field6": base.util.prepend([3, 4]),
        },
        key="test_key",
    )
    assert updated_item == TestItemDict(
        key="test_key",
        field1="updated_value",
        field2=item["field2"],
        field3=item["field3"] + 2,
        field4=item["field4"] - 2,
        field5=[*item["field5"], "baz"],
        field6=[3, 4, *item["field6"]],
        field7=item["field7"],
    )


def test_query(base: Base[TestItemDict]) -> None:
    items = [create_test_item(f"test_key_{i}") for i in range(3)]
    base.put(*items)
    response = base.query()
    assert response == FetchResponse(count=3, last_key=None, items=items)
