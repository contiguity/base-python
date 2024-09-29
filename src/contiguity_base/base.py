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
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            print(
                f"HTTP error! status: {e.response.status_code}, body: {e.response.text}")
        except requests.exceptions.RequestException as e:
            if self.db.debug:
                print(f"Request failed: {str(e)}")
        return None

    def put(self, data: Union[Dict, List[Dict]], key: Optional[str] = None, expire_in: Optional[int] = None, expire_at: Optional[Union[datetime, str]] = None) -> Optional[Dict]:
        path = "/items"

        if isinstance(data, dict):
            if key:
                data['key'] = key
            items = [data]
        elif isinstance(data, list):
            items = data
        else:
            raise ValueError(
                "Data must be either a dictionary or a list of dictionaries")

        request_body = {"items": items}

        if expire_in is not None:
            request_body["expireIn"] = expire_in

        if expire_at is not None:
            request_body["expireAt"] = expire_at

        return self._fetch("PUT", path, request_body)

    def get(self, key: str) -> Optional[Dict]:
        return self._fetch("GET", f"/items/{key}")

    def delete(self, key: str) -> Optional[Dict]:
        return self._fetch("DELETE", f"/items/{key}")

    def update(self, updates: Dict[str, Any], key: str, expire_in: Optional[int] = None, expire_at: Optional[Union[datetime, str]] = None) -> Optional[Dict]:
        processed_updates = {
            field: (value if isinstance(value, dict) and "__op" in value else {"__op": "set", "value": value})
            for field, value in updates.items()
        }
        
        request_body = {"updates": processed_updates}

        if expire_in is not None:
            request_body["expireIn"] = expire_in
        
        if expire_at is not None:
            if isinstance(expire_at, datetime):
                request_body["expireAt"] = expire_at.isoformat()
            else:
                request_body["expireAt"] = expire_at

        return self._fetch("PATCH", f"/items/{key}", request_body)

    def fetch(self, query: Optional[Dict] = None, limit: Optional[int] = None, last: Optional[str] = None) -> Dict[str, Any]:
        query_params = {
            "query": query,
            "limit": limit,
            "last": last
        }
        query_params = {k: v for k, v in query_params.items() if v is not None}

        if self.db.debug:
            print(f"Fetch params sent to server: {query_params}")

        response = self._fetch("POST", "/query", query_params)
        return {
            "items": response.get("items", []),
            "last": response.get("last"),
            "count": response.get("count", 0)
        }


    def insert(self, data: Dict, key: Optional[str] = None, expire_in: Optional[int] = None, expire_at: Optional[Union[datetime, str]] = None) -> Optional[Dict]:
        path = "/items"
        
        if key:
            data['key'] = key

        request_body = {"item": data}

        if expire_in is not None:
            request_body["expireIn"] = expire_in
        
        if expire_at is not None:
            if isinstance(expire_at, datetime):
                request_body["expireAt"] = expire_at.isoformat()
            else:
                request_body["expireAt"] = expire_at

        return self._fetch("POST", path, request_body)

class Contiguity:
    def __init__(self, api_key: str, project_id: str, debug: bool = False):
        self.api_key = api_key
        self.project_id = project_id
        self.base_url = "https://api.base.contiguity.co/v1"
        self.debug = debug

    def Base(self, name: str) -> Base:
        return Base(self, name)

def connect(api_key: str, project_id: str, debug: bool = False) -> Contiguity:
    return Contiguity(api_key, project_id, debug)