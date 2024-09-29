# ruff: noqa: S101, PLR2004
from collections.abc import Generator, Sequence
from typing import Any

import pytest
from pydantic import BaseModel

from contiguity_base.base import Base, FetchResponse, ItemConflictError


class TestItem(BaseModel):
    key: str
    value: str


@pytest.fixture
def base() -> Generator[Base[TestItem], Any, None]:
    base = Base("test_base", item_type=TestItem)
    for item in base.fetch().items:
        base.delete(item.key)
    yield base
    for item in base.fetch().items:
        base.delete(item.key)


def test_insert_item(base: Base[TestItem]) -> None:
    item = TestItem(key="test_key", value="test_value")
    inserted_item = base.insert(item)
    assert inserted_item.key == item.key
    assert inserted_item.value == item.value


def test_insert_existing_item(base: Base[TestItem]) -> None:
    item = TestItem(key="test_key", value="test_value")
    base.insert(item)
    with pytest.raises(ItemConflictError):
        base.insert(item)


def test_get_item(base: Base[TestItem]) -> None:
    item = TestItem(key="test_key", value="test_value")
    base.insert(item)
    fetched_item = base.get("test_key")
    assert fetched_item
    assert fetched_item.key == item.key
    assert fetched_item.value == item.value


def test_get_nonexistent_item(base: Base[TestItem]) -> None:
    with pytest.warns(DeprecationWarning):
        assert base.get("nonexistent_key") is None


def test_delete_item(base: Base[TestItem]) -> None:
    item = TestItem(key="test_key", value="test_value")
    base.insert(item)
    base.delete("test_key")
    with pytest.warns(DeprecationWarning):
        assert base.get("test_key") is None


def test_put_items(base: Base[TestItem]) -> None:
    items = [TestItem(key=f"test_key_{i}", value=f"test_value_{i}") for i in range(3)]
    response = base.put(*items)
    assert isinstance(response, Sequence)
    assert len(response) == 3


def test_fetch_items(base: Base[TestItem]) -> None:
    items = [TestItem(key=f"test_key_{i}", value=f"test_value_{i}") for i in range(3)]
    base.put(*items)
    response = base.fetch()
    assert isinstance(response, FetchResponse)
    assert len(response.items) == 3


def test_update_item(base: Base[TestItem]) -> None:
    item = TestItem(key="test_key", value="test_value")
    base.insert(item)
    base.update({"value": "updated_value"}, key="test_key")
    updated_item = base.get("test_key")
    assert updated_item
    assert updated_item.value == "updated_value"
