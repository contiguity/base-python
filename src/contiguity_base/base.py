# TODO @lemonyte: todo list. # noqa: TD003, FIX002
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

from httpx import HTTPStatusError
from pydantic import BaseModel, TypeAdapter
from pydantic import JsonValue as DataType
from typing_extensions import deprecated

from contiguity_base._auth import get_base_token, get_project_id
from contiguity_base._client import ApiClient, ApiError

if TYPE_CHECKING:
    from httpx import Response as HttpxResponse
    from typing_extensions import Self

TimestampType = Union[int, datetime]
QueryType = Union[DataType, list[DataType]]

ItemType = Union[Mapping, BaseModel]
ItemT = TypeVar("ItemT", bound=ItemType)
DefaultItemT = TypeVar("DefaultItemT")


class _Unset:
    pass


_UNSET = _Unset()


class BaseItem(BaseModel):
    key: str


class ItemConflictError(ApiError):
    pass


class ItemNotFoundError(ApiError):
    def __init__(self, key: str, *args: object) -> None:
        super().__init__(f"key '{key}' not found", *args)


class FetchResponse(BaseModel, Generic[ItemT]):
    count: int = 0
    last_key: Union[str, None] = None  # noqa: UP007 Pydantic doesn't support `X | Y` syntax in Python 3.9.
    items: list[ItemT] = []


class _UpdatePayload(BaseModel):
    set: dict[str, DataType] = {}
    increment: dict[str, int] = {}
    append: dict[str, Sequence[DataType]] = {}
    prepend: dict[str, Sequence[DataType]] = {}
    delete: list[str] = []

    @classmethod
    def from_updates_mapping(cls: type[Self], updates: Mapping[str, DataType | _UpdateOperation], /) -> Self:
        set = {}
        increment = {}
        append = {}
        prepend = {}
        delete = []
        for attr, value in updates.items():
            if isinstance(value, _UpdateOperation):
                if isinstance(value, _Trim):
                    delete.append(attr)
                elif isinstance(value, _Increment):
                    increment[attr] = value.value
                elif isinstance(value, _Append):
                    append[attr] = value.value
                elif isinstance(value, _Prepend):
                    prepend[attr] = value.value
            else:
                set[attr] = value
        return cls(
            set=set,
            increment=increment,
            append=append,
            prepend=prepend,
            delete=delete,
        )


class _UpdateOperation:
    pass


class _Trim(_UpdateOperation):
    pass


class _Increment(_UpdateOperation):
    def __init__(self: _Increment, value: int = 1, /) -> None:
        self.value = value


class _Append(_UpdateOperation):
    def __init__(self: _Append, value: DataType, /) -> None:
        if isinstance(value, (list, tuple)):
            self.value = value
        else:
            self.value = [value]


class _Prepend(_Append):
    pass


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
        item_type: type[ItemT] = Mapping,
        base_token: str | None = None,
        project_id: str | None = None,
        host: str | None = None,
        api_version: str = "v1",
        json_decoder: type[json.JSONDecoder] = json.JSONDecoder,
    ) -> None: ...

    @overload
    @deprecated("The `project_key` parameter has been renamed to `base_token`.")
    def __init__(
        self: Self,
        name: str,
        /,
        *,
        item_type: type[ItemT] = Mapping,
        project_key: str | None = None,
        project_id: str | None = None,
        host: str | None = None,
        api_version: str = "v1",
        json_decoder: type[json.JSONDecoder] = json.JSONDecoder,
    ) -> None: ...

    def __init__(  # noqa: PLR0913
        self: Self,
        name: str,
        /,
        *,
        item_type: type[ItemT] = Mapping,
        base_token: str | None = None,
        project_key: str | None = None,  # Deprecated.
        project_id: str | None = None,
        host: str | None = None,
        api_version: str = "v1",
        json_decoder: type[json.JSONDecoder] = json.JSONDecoder,  # Only used when item_type is not a Pydantic model.
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
        self.json_decoder = json_decoder
        self.util = _Updates()
        self._client = ApiClient(
            base_url=f"https://{self.host}/{api_version}/{self.project_id}/{self.name}",
            api_key=self.base_token,
            timeout=300,
        )

    def _response_as_item_types(self: Self, response: HttpxResponse) -> Sequence[ItemT]:
        try:
            response.raise_for_status()
        except HTTPStatusError as exc:
            raise ApiError(exc.response.text) from exc
        if issubclass(self.item_type, BaseModel):
            return TypeAdapter(list[self.item_type]).validate_json(response.content)
        # TODO @lemonyte: support TypedDict and parameterized generics. # noqa: TD003, FIX002
        if isinstance((data := response.json(cls=self.json_decoder)), list) and all(
            isinstance(item, self.item_type) for item in data
        ):
            return data
        msg = f"failed to convert data to item type {self.item_type}\n\t{data}"
        raise ValueError(msg)

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
    def get(self: Self, key: str, default: ItemT, /) -> ItemT: ...

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

        if not (returned_item := self._response_as_item_types(response)):
            msg = "expected a single item, got an empty response"
            raise ApiError(msg)
        return returned_item[0]

    def delete(self: Self, key: str, /) -> None:
        """Delete an item from the Base."""
        if not key:
            msg = f"invalid key '{key}'"
            raise ValueError(msg)

        key = quote(key, safe="")
        response = self._client.delete(f"/items/{key}")
        try:
            response.raise_for_status()
        except HTTPStatusError as exc:
            raise ApiError(exc.response.text) from exc

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

        if not (returned_item := self._response_as_item_types(response)):
            msg = "expected a single item, got an empty response"
            raise ApiError(msg)
        return returned_item[0]

    def put(
        self: Self,
        *items: ItemT,
        expire_in: int | None = None,
        expire_at: TimestampType | None = None,
    ) -> Sequence[ItemT]:
        """store (put) an item in the database. Overrides an item if key already exists.
        `key` could be provided as function argument or a field in the data dict.
        If `key` is not provided, the server will generate a random 12 chars key.
        """
        if len(items) > self.PUT_LIMIT:
            msg = f"cannot put more than {self.PUT_LIMIT} items at a time"
            raise ValueError(msg)

        item_dicts = [self._insert_expires_attr(item, expire_in=expire_in, expire_at=expire_at) for item in items]
        response = self._client.put("/items", json={"items": item_dicts})
        return self._response_as_item_types(response)

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
            payload["query"] = query if isinstance(query, (list, tuple)) else [query]

        response = self._client.post("/query", json=payload)
        try:
            response.raise_for_status()
        except HTTPStatusError as exc:
            raise ApiError(exc.response.text) from exc
        return FetchResponse.model_validate_json(response.content)

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
        if not updates:
            msg = "no updates provided"
            raise ValueError(msg)

        payload = _UpdatePayload.from_updates_mapping(updates)
        payload.set = self._insert_expires_attr(
            payload.set,
            expire_in=expire_in,
            expire_at=expire_at,
        )

        key = quote(key, safe="")
        response = self._client.patch(f"/items/{key}", json=payload.model_dump())
        if response.status_code == HTTPStatus.NOT_FOUND:
            raise ItemNotFoundError(key)

        if not (returned_item := self._response_as_item_types(response)):
            msg = "expected a single item, got an empty response"
            raise ApiError(msg)
        return returned_item[0]
