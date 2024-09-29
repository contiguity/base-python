# ruff: noqa: TD003, FIX002, ERA001, T201
# Remove above ignores when issues are fixed.
# TODO @lemonyte: todo list.
# - [ ] custom json encoder support
# - [ ] new docstrings
# - [ ] proper tests
# - [ ] add async
# - [ ] add drive support
# - [ ] merge into main sdk

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import TYPE_CHECKING, Generic, TypeVar, Union, overload
from urllib.parse import quote
from warnings import warn

from pydantic import BaseModel
from pydantic import JsonValue as DataType
from typing_extensions import deprecated

from contiguity_base._auth import get_base_token, get_project_id
from contiguity_base._client import Client

if TYPE_CHECKING:
    from httpx import Response as HttpxResponse
    from typing_extensions import Self

TimestampType = Union[int, datetime]
QueryType = Union[DataType, list[DataType]]

ItemType = Union[Mapping[str, DataType], BaseModel]
ItemT = TypeVar("ItemT", bound=ItemType)
DefaultItemT = TypeVar("DefaultItemT", bound=ItemType)

ModelT = TypeVar("ModelT", bound=BaseModel)
DataT = TypeVar("DataT", bound=DataType)


class _Unset:
    pass


_UNSET = _Unset()


class BaseItem(BaseModel):
    key: str


class ItemConflictError(Exception):
    pass


class ItemNotFoundError(Exception):
    def __init__(self, key: str, *args: object) -> None:
        super().__init__(f"key '{key}' not found", *args)


class FetchResponse(BaseModel, Generic[ItemT]):
    count: int = 0
    last_key: Union[str, None] = None  # noqa: UP007 Pydantic doesn't support `X | Y` syntax in Python 3.9.
    items: list[ItemT] = []


class _UpdateOperation:
    def __init__(self: _UpdateOperation) -> None:
        self.value = None

    def as_dict(self: _UpdateOperation) -> dict[str, DataType]:
        return {"__op": self.__class__.__name__.lower().replace("_", ""), "value": self.value}


class _Trim(_UpdateOperation):
    def as_dict(self: _UpdateOperation) -> dict[str, DataType]:
        return {"__op": "trim"}


class _Increment(_UpdateOperation):
    def __init__(self: _Increment, value: int = 1, /) -> None:
        self.value = value


class _Append(_UpdateOperation):
    def __init__(self: _Append, value: DataType, /) -> None:
        self.value = value
        # TODO @lemonyte: The API does not support multi-value append and prepend yet.
        # Uncomment this here and in _Prepend when it does.
        # if not isinstance(value, Sequence):
        #     # Extra type hint because type checkers can be stupid sometimes.
        #     self.value: DataType = [value]


class _Prepend(_UpdateOperation):
    def __init__(self: _Prepend, value: DataType, /) -> None:
        self.value = value
        # if not isinstance(value, Sequence):
        #     self.value: DataType = [value]


class _Updates:
    @staticmethod
    def trim() -> _Trim:
        return _Trim()

    @staticmethod
    def increment(value: int = 1, /) -> _Increment:
        return _Increment(value)

    @staticmethod
    def append(value: DataType, /) -> _Append:
        return _Append(value)

    @staticmethod
    def prepend(value: DataType, /) -> _Prepend:
        return _Prepend(value)


class Base(Generic[ItemT]):
    EXPIRES_ATTRIBUTE = "__expires"
    PUT_LIMIT = 30

    @overload
    def __init__(
        self: Self,
        name: str,
        /,
        *,
        item_type: type[ItemT] = Mapping[str, DataType],
        base_token: str | None = None,
        project_id: str | None = None,
        host: str | None = None,
        api_version: str = "v1",
        json_encoder: type[json.JSONEncoder] = json.JSONEncoder,
        json_decoder: type[json.JSONDecoder] = json.JSONDecoder,
    ) -> None: ...

    @overload
    @deprecated("The `project_key` parameter has been renamed to `base_token`.")
    def __init__(
        self: Self,
        name: str,
        /,
        *,
        item_type: type[ItemT] = Mapping[str, DataType],
        project_key: str | None = None,
        project_id: str | None = None,
        host: str | None = None,
        api_version: str = "v1",
        json_encoder: type[json.JSONEncoder] = json.JSONEncoder,
        json_decoder: type[json.JSONDecoder] = json.JSONDecoder,
    ) -> None: ...

    def __init__(  # noqa: PLR0913
        self: Self,
        name: str,
        /,
        *,
        item_type: type[ItemT] = Mapping[str, DataType],
        base_token: str | None = None,
        project_key: str | None = None,  # Deprecated.
        project_id: str | None = None,
        host: str | None = None,
        api_version: str = "v1",
        json_encoder: type[json.JSONEncoder] = json.JSONEncoder,
        json_decoder: type[json.JSONDecoder] = json.JSONDecoder,
    ) -> None:
        if not name:
            msg = f"invalid name '{name}'"
            raise ValueError(msg)

        self.name = name
        self.item_type = item_type
        self.base_token = base_token or project_key or get_base_token()
        self.project_id = project_id or get_project_id()
        self.host = host or os.getenv("CONTIGUITY_BASE_HOST") or "api.base.contiguity.co"
        self.api_version = api_version
        self.json_encoder = json_encoder
        self.json_decoder = json_decoder
        self.util = _Updates()
        self._client = Client(
            base_url=f"https://{self.host}/{api_version}/{self.project_id}/{self.name}",
            api_key=self.base_token,
            timeout=300,
        )

    def _data_as_item_type(self: Self, data: Mapping[str, DataType]) -> ItemT:
        print("data:", data)
        if issubclass(self.item_type, BaseModel):
            return self.item_type.model_validate(data)
        # TODO @lemonyte: support dicts as well as BaseModel subclasses.
        # if isinstance(data, self.item_type.__args__[0]):
        #     return data
        msg = f"failed to convert data to item type {self.item_type}"
        raise ValueError(msg)

    def _response_as_item_type(self: Self, response: HttpxResponse) -> ItemT | Sequence[ItemT]:
        data = response.raise_for_status().json(cls=self.json_decoder)
        if isinstance(data, Sequence):
            return [self._data_as_item_type(item) for item in data]
        return self._data_as_item_type(data)

    def _insert_expires_attr(
        self: Self,
        item: ItemT | Mapping[str, DataType],
        expire_in: int | None = None,
        expire_at: TimestampType | None = None,
    ) -> dict[str, DataType]:
        if expire_in and expire_at:
            msg = "cannot use both expire_in and expire_at"
            raise ValueError(msg)

        item_dict = item.model_dump() if isinstance(item, BaseModel) else dict(item)

        if not expire_in and not expire_at:
            return item_dict

        if expire_in:
            expire_at = datetime.now(tz=timezone.utc) + timedelta(seconds=expire_in)

        if isinstance(expire_at, datetime):
            expire_at = int(expire_at.replace(microsecond=0).timestamp())

        if not isinstance(expire_at, int):
            msg = "expire_at should be a datetime or int"
            raise TypeError(msg)

        item_dict[self.EXPIRES_ATTRIBUTE] = expire_at
        return item_dict

    @overload
    def get(self: Self, key: str, /) -> ItemT | None: ...

    @overload
    def get(self: Self, key: str, default: DefaultItemT, /) -> ItemT | DefaultItemT: ...

    def get(self: Self, key: str, default: DefaultItemT | _Unset = _UNSET, /) -> ItemT | DefaultItemT | None:
        if not key:
            msg = f"invalid key '{key}'"
            raise ValueError(msg)

        key = quote(key, safe="")
        response = self._client.get(f"/items/{key}")

        if response.status_code == HTTPStatus.NOT_FOUND:
            if not isinstance(default, _Unset):
                return default
            msg = (
                "ItemNotFoundError will be raised in the future."
                " To receive None for non-existent keys, set default=None."
            )
            warn(DeprecationWarning(msg), stacklevel=2)
            return None
            # raise ItemNotFoundError(key)

        # TODO @lemonyte: due to the API returning both a single item and a list of items,
        # we need to check the response type.
        # Remove when the API is fixed to always return a list of items.
        returned_item = self._response_as_item_type(response)
        if isinstance(returned_item, Sequence):
            # this shouldn't happen, it's just here until the API is fixed
            msg = "expected a single item, got a list of items"
            raise TypeError(msg)
        return returned_item

    def delete(self: Self, key: str, /, *, ignore_missing: bool = False) -> None:
        """Delete an item from the Base."""
        if not key:
            msg = f"invalid key '{key}'"
            raise ValueError(msg)

        key = quote(key, safe="")
        response = self._client.delete(f"/items/{key}")
        if response.status_code == HTTPStatus.NOT_FOUND and not ignore_missing:
            raise ItemNotFoundError(key)
        response.raise_for_status()

    def insert(
        self: Self,
        item: ItemT,
        /,
        *,
        expire_in: int | None = None,
        expire_at: TimestampType | None = None,
    ) -> ItemT:
        item_dict = self._insert_expires_attr(item, expire_in=expire_in, expire_at=expire_at)
        response = self._client.post("/items", json={"item": item_dict})

        if response.status_code == HTTPStatus.CONFLICT:
            msg = f"item with key '{item_dict.get('key')}' already exists"
            raise ItemConflictError(msg)

        # TODO @lemonyte: due to the API returning both a single item and a list of items,
        # we need to check the response type.
        # Remove when the API is fixed to always return a list of items.
        returned_item = self._response_as_item_type(response)
        if isinstance(returned_item, Sequence):
            # this shouldn't happen, it's just here until the API is fixed
            msg = "expected a single item, got a list of items"
            raise TypeError(msg)
        return returned_item

    def put(
        self: Self,
        *items: ItemT,
        expire_in: int | None = None,
        expire_at: TimestampType | None = None,
    ) -> ItemT | Sequence[ItemT]:
        """store (put) an item in the database. Overrides an item if key already exists.
        `key` could be provided as function argument or a field in the data dict.
        If `key` is not provided, the server will generate a random 12 chars key.
        """
        if len(items) > self.PUT_LIMIT:
            msg = f"cannot put more than {self.PUT_LIMIT} items at a time"
            raise ValueError(msg)

        item_dicts = [self._insert_expires_attr(item, expire_in=expire_in, expire_at=expire_at) for item in items]
        response = self._client.put("/items", json={"items": item_dicts})
        return self._response_as_item_type(response)

    @deprecated("This method will be removed in the future. You can pass multiple items to `put`.")
    def put_many(
        self: Self,
        items: Sequence[ItemT],
        /,
        *,
        expire_in: int | None = None,
        expire_at: TimestampType | None = None,
    ) -> ItemT | Sequence[ItemT]:
        return self.put(*items, expire_in=expire_in, expire_at=expire_at)

    def fetch(
        self: Self,
        query: QueryType | None = None,
        /,
        *,
        limit: int = 1000,
        last: str | None = None,
    ) -> FetchResponse[ItemT]:
        """fetch items from the database.
        `query` is an optional filter or list of filters. Without filter, it will return the whole db.
        """

        payload = {
            "limit": limit,
            "last": last,
        }

        if query:
            payload["query"] = query if isinstance(query, list) else [query]

        response = self._client.post("/query", json=payload)
        response_json = response.raise_for_status().json(cls=self.json_decoder)
        return FetchResponse(
            count=response_json.get("count", 0),
            last_key=response_json.get("last", None),
            items=[self._data_as_item_type(item) for item in response_json.get("items", [])],
        )

    def update(
        self: Self,
        updates: Mapping[str, DataType | _UpdateOperation],
        /,
        *,
        key: str,
        expire_in: int | None = None,
        expire_at: TimestampType | None = None,
    ) -> ItemT:
        """update an item in the database
        `updates` specifies the attribute names and values to update,add or remove
        `key` is the key of the item to be updated
        """
        if not key:
            msg = f"invalid key '{key}'"
            raise ValueError(msg)

        payload = {
            "updates": {
                field: (value.as_dict() if isinstance(value, _UpdateOperation) else {"__op": "set", "value": value})
                for field, value in updates.items()
            },
        }

        # payload = self._insert_expires_attr(
        #     payload,
        #     expire_in=expire_in,
        #     expire_at=expire_at,
        # )

        # TODO @lemonyte: Remove when the API adds support for __expires.
        if expire_in is not None:
            payload["expireIn"] = expire_in  # type: ignore[assignment]
        if expire_at is not None:
            if isinstance(expire_at, datetime):
                payload["expireAt"] = expire_at.isoformat()  # type: ignore[assignment]
            else:
                payload["expireAt"] = expire_at  # type: ignore[assignment]

        key = quote(key, safe="")
        response = self._client.patch(f"/items/{key}", json=payload)
        if response.status_code == HTTPStatus.NOT_FOUND:
            raise ItemNotFoundError(key)

        # TODO @lemonyte: due to the API returning both a single item and a list of items,
        # we need to check the response type.
        # Remove when the API is fixed to always return a list of items.
        returned_item = self._response_as_item_type(response)
        if isinstance(returned_item, Sequence):
            # this shouldn't happen, it's just here until the API is fixed
            msg = "expected a single item, got a list of items"
            raise TypeError(msg)
        return returned_item
