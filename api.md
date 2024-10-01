# Base API

## GET /items/{key}

SDK method: `get(key: str) -> Item`

Response `200`:
Returns a single item.

```json
{
    "key": "foo",
    "field1": "bar"
    // ...other item fields
}
```

Response `404`:
Key does not exist.

```text
No content
```

## DELETE /items/{key}

SDK method: `delete(key: str) -> None`

Response `204`:
Returns nothing.

```text
No content
```

## POST /items

SDK method: `insert(item: Item) -> Item`

Request body:

```json
{
    "item": {
        "key": "foo",
        "field1": "bar",
        // ...other item fields
        "__expires": 1727765807 // optional Unix timestamp
    }
}
```

Response `201`:
Returns a list of items.

```json
[
    {
        "key": "foo",
        "field1": "bar"
        // ...other item fields
    }
    // ...other items
]
```

Response `409`:
Key already exists.

```text
No content
```

## PUT /items

SDK method: `put(items: Item[]) -> Item[]`

Request body:

```json
{
    "items": [
        {
            "key": "foo",
            "field1": "bar",
            // ...other item fields
            "__expires": 1727765807 // optional Unix timestamp
        }
        // ...other items
    ]
}
```

Response `201`:
Returns a list of items.

```json
[
    {
        "key": "foo",
        "field1": "bar"
        // ...other item fields
    }
    // ...other items
]
```

## PATCH /items/{key}

SDK method: `update(updates: Mapping, key: str) -> Item`

Request body:

```json
{
    "set": {
        "field1": "bar",
        // ...other item fields
        "__expires": 1727765807 // optional Unix timestamp
    },
    "increment": {
        "field2": 1,
        "field3": -2
    },
    "append": {
        "field4": ["baz"]
    },
    "prepend": {
        "field5": ["foo", "bar"]
    },
    "delete": ["field6"]
}
```

Response `200`:
Returns a single item.

```json
{
    "key": "foo",
    "field1": "bar"
    // ...other item fields
}
```

Response `404`:
Key does not exist.

```text
No content
```

## GET /query

SDK method: `fetch(*query: Query) -> Item[]`

Request body:

```json
{
    "limit": 10,
    "last_key": "foo",
    "query": [
        {
            "field1": "foo",
            "field4?contains": "bar"
            // multiple conditions are ANDed
        },
        {
            "field3?gt": 2
        }
        // multiple queries are ORed
    ]
}
```

Response `200`:
Returns a list of items.

```json
[
    {
        "key": "foo",
        "field1": "bar"
        // ...other item fields
    }
    // ...other items
]
```
