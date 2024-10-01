# ruff: noqa: S101, PLR2004
from collections.abc import Generator, Mapping
from typing import Any

import pytest
from pydantic import JsonValue

from contiguity_base.base import Base, FetchResponse, ItemConflictError
from tests import random_string

DictItemType = Mapping[str, JsonValue]


@pytest.fixture
def base() -> Generator[Base[DictItemType], Any, None]:
    base = Base("test_base", item_type=DictItemType)
    for item in base.query().items:
        base.delete(str(item["key"]))
    yield base
    for item in base.query().items:
        base.delete(str(item["key"]))


def test_get(base: Base[DictItemType]) -> None:
    item = {"key": "test_key", "value": random_string()}
    base.insert(item)
    fetched_item = base.get("test_key")
    assert fetched_item == item


def test_get_nonexistent(base: Base[DictItemType]) -> None:
    with pytest.warns(DeprecationWarning):
        assert base.get("nonexistent_key") is None


def test_delete(base: Base[DictItemType]) -> None:
    item = {"key": "test_key", "value": random_string()}
    base.insert(item)
    base.delete("test_key")
    with pytest.warns(DeprecationWarning):
        assert base.get("test_key") is None


def test_insert(base: Base[DictItemType]) -> None:
    item = {"key": "test_key", "value": random_string()}
    inserted_item = base.insert(item)
    assert inserted_item == item


def test_insert_existing(base: Base[DictItemType]) -> None:
    item = {"key": "test_key", "value": random_string()}
    base.insert(item)
    with pytest.raises(ItemConflictError):
        base.insert(item)


def test_put(base: Base[DictItemType]) -> None:
    items = [{"key": f"test_key_{i}", "field1": f"test_value_{i}"} for i in range(3)]
    response = base.put(*items)
    assert response == items


def test_update(base: Base[DictItemType]) -> None:
    item = {
        "key": "test_key",
        "field1": random_string(),
        "field2": random_string(),
        "field3": 1,
        "field4": 0,
        "field5": ["foo", "bar"],
        "field6": [1, 2],
        "field7": {"foo": "bar"},
    }
    base.insert(item)
    updated_item = base.update(
        {
            "field1": "updated_value",
            "field2": base.util.trim(),
            "field3": base.util.increment(2),
            "field4": base.util.increment(-2),
            "field5": base.util.append("baz"),
            "field6": base.util.append([3, 4]),
        },
        key="test_key",
    )
    assert updated_item == {
        "key": "test_key",
        "field1": "updated_value",
        "field2": "",
        "field3": 3,
        "field4": -2,
        "field5": ["foo", "bar", "baz"],
        "field6": [1, 2, 3, 4],
        "field7": {"foo": "bar"},
    }


def test_fetch(base: Base[DictItemType]) -> None:
    items = [{"key": f"test_key_{i}", "field1": f"test_value_{i}"} for i in range(3)]
    base.put(*items)
    response = base.query()
    assert response == FetchResponse(count=3, last_key=None, items=items)
