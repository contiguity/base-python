import requests
from typing import Union, List, Dict, Any, Optional
from datetime import datetime


class Util:
    @staticmethod
    def increment(value: int = 1) -> Dict[str, Any]:
        return {"__op": "increment", "value": value}

    @staticmethod
    def append(value: Any) -> Dict[str, Any]:
        return {"__op": "append", "value": value}

    @staticmethod
    def prepend(value: Any) -> Dict[str, Any]:
        return {"__op": "prepend", "value": value}

    @staticmethod
    def trim() -> Dict[str, str]:
        return {"__op": "trim"}


class Base:
    def __init__(self, db: 'Contiguity', name: str):
        self.db = db
        self.name = name
        self.util = Util()

    def _fetch(self, method: str, path: str, body: Optional[Dict] = None) -> Optional[Dict]:
        url = f"{self.db.base_url}/{self.db.project_id}/{self.name}{path}"
        headers = {
            "x-api-key": self.db.api_key,
            "Content-Type": "application/json",
        }

        if self.db.debug:
            print(f"Sending {method} request to: {url}")

        try:
            response = requests.request(
                method, url, headers=headers, json=body)
            if not response.ok:
                if response.status_code == 404:
                    return None
                print(f"HTTP error! status: {response.status_code}, body: {response.text}")
                return None
            return response.json()
        except requests.exceptions.RequestException as e:
            if self.db.debug:
                print(f"Request failed: {str(e)}")
            return None

    def calculate_expires(self, expire_in: Optional[int], expire_at: Optional[Union[datetime, str]]) -> Optional[int]:
        if expire_at:
            if isinstance(expire_at, datetime):
                return int(expire_at.timestamp())
            else:
                return int(datetime.fromisoformat(expire_at).timestamp())
        elif expire_in:
            return int(datetime.now().timestamp()) + expire_in
        return None

    def put(self, items: Union[Dict, List[Dict]], key: Optional[str] = None, expire_in: Optional[int] = None, expire_at: Optional[Union[datetime, str]] = None, options: Optional[Dict] = None) -> Optional[Dict]:
        path = "/items"
        options = options or {}

        # Handle both direct parameters and options
        expire_in = expire_in or options.get('expireIn')
        expire_at = expire_at or options.get('expireAt')

        if isinstance(items, dict):
            items_array = [{"key": key, **items}] if key else [items]
        else:
            items_array = items

        for item in items_array:
            expires = self.calculate_expires(expire_in, expire_at)
            if expires:
                item['__expires'] = expires

        return self._fetch("PUT", path, {"items": items_array})

    def insert(self, data: Dict, key: Optional[str] = None, expire_in: Optional[int] = None, expire_at: Optional[Union[datetime, str]] = None, options: Optional[Dict] = None) -> Optional[Dict]:
        path = "/items"
        options = options or {}

        if key:
            data['key'] = key

        request_body = {"item": data}

        # Handle both direct parameters and options
        expire_in = expire_in or options.get('expireIn')
        expire_at = expire_at or options.get('expireAt')

        expires = self.calculate_expires(expire_in, expire_at)
        if expires:
            request_body["item"]["__expires"] = expires

        return self._fetch("POST", path, request_body)

    def get(self, key: str) -> Optional[Dict]:
        return self._fetch("GET", f"/items/{key}")

    def delete(self, key: str) -> Optional[Dict]:
        return self._fetch("DELETE", f"/items/{key}")

    def update(self, updates: Dict[str, Any], key: str, options: Optional[Dict] = None) -> Optional[Dict]:
        options = options or {}
        processed_updates = {
            "set": {},
            "increment": {},
            "append": {},
            "prepend": {},
            "delete": []
        }

        for field, value in updates.items():
            if isinstance(value, dict) and "__op" in value:
                op = value["__op"]
                if op == "increment":
                    processed_updates["increment"][field] = value["value"]
                elif op == "append":
                    processed_updates["append"][field] = value["value"]
                elif op == "prepend":
                    processed_updates["prepend"][field] = value["value"]
                elif op == "delete":
                    processed_updates["delete"].append(field)
                else:
                    processed_updates["set"][field] = value["value"]
            else:
                processed_updates["set"][field] = value

        expires = self.calculate_expires(
            options.get('expireIn'), options.get('expireAt'))
        if expires:
            processed_updates["set"]["__expires"] = expires

        return self._fetch("PATCH", f"/items/{key}", {"updates": processed_updates})

    def fetch(self, query: Optional[Dict] = None, limit: Optional[int] = None, last: Optional[str] = None, options: Optional[Dict] = None) -> Dict[str, Any]:
        options = options or {}

        # Handle both direct parameters and options
        limit = limit or options.get('limit')
        last = last or options.get('last')

        query_params = {
            "query": query,
            "limit": limit,
            "last": last
        }
        query_params = {k: v for k, v in query_params.items() if v is not None}

        if self.db.debug:
            print(f"Fetch params sent to server: {query_params}")

        response = self._fetch("POST", "/query", query_params)
        if response:
            return {
                "items": response.get("items", []),
                "last": response.get("last"),
                "count": response.get("count", 0)
            }
        return {"items": [], "last": None, "count": 0}

    def put_many(self, items: List[Dict]) -> Optional[Dict]:
        if not isinstance(items, list) or len(items) == 0:
            raise ValueError("put_many requires a non-empty list of items")
        return self.put(items)


class Contiguity:
    def __init__(self, api_key: str, project_id: str, debug: bool = False):
        self.api_key = api_key
        self.project_id = project_id
        self.base_url = "https://base.api.contiguity.co/v1"
        self.debug = debug

    def Base(self, name: str) -> Base:
        return Base(self, name)


def connect(api_key: str, project_id: str, debug: bool = False) -> Contiguity:
    return Contiguity(api_key, project_id, debug)
