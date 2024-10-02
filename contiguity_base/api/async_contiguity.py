from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from httpx import AsyncClient, RequestError, Response

from contiguity_base.base import BaseContiguity


class AsyncContiguity(BaseContiguity):
    class Base(BaseContiguity.Base):
        async def _fetch(self, method: str, path: str, body: Optional[Dict] = None) -> Optional[Dict]:
            url = f"{self.db.base_url}/{self.db.project_id}/{self.name}{path}"
            headers = {
                "x-api-key": self.db.api_key,
                "Content-Type": "application/json",
            }

            if self.db.debug:
                print(f"Sending {method} request to: {url}")
                
            try:
                response: Response = await self.db._client.request(method, url, headers=headers, json=body)
                if 200 <= response.status_code < 400:
                    return response.json()
                if response.status_code == 404:
                    return None
                if self.db.debug:
                    print(f"HTTP error! status: {response.status_code}, body: {response.text}")
                return None
            except RequestError as e:
                if self.db.debug:
                    print(f"Request failed: {str(e)}")
                return None
        
        async def put(self, items: Union[Dict, List[Dict]], key: Optional[str] = None, expire_in: Optional[int] = None, expire_at: Optional[Union[datetime, str]] = None, options: Optional[Dict] = None) -> Optional[Dict]:
            path = "/items"
            options = options or {}

            # Handle both direct parameters and options
            expire_in, expire_at = self.get_expire(expire_in, expire_at, options)

            if isinstance(items, dict):
                items_array = [{"key": key, **items}] if key else [items]
            else:
                items_array = items

            for item in items_array:
                expires = self.calculate_expires(expire_in, expire_at)
                if expires:
                    item["__expires"] = expires

            return await self._fetch("PUT", path, {"items": items_array})

        async def insert(self, data: Dict, key: Optional[str] = None, expire_in: Optional[int] = None, expire_at: Optional[Union[datetime, str]] = None, options: Optional[Dict] = None) -> Optional[Dict]:
            path = "/items"
            options = options or {}

            if key:
                data["key"] = key
            
            request_body = {"item": data}

            # Handle both direct parameters and options
            expire_in, expire_at = self.get_expire(expire_in, expire_at, options)

            expires = self.calculate_expires(expire_in, expire_at)
            if expires:
                request_body["item"]["__expires"] = expires

            return await self._fetch("POST", path, request_body)

        async def get(self, key: str) -> Optional[Dict]:
            return await self._fetch("GET", f"/items/{key}")

        async def delete(self, key: str) -> Optional[Dict]:
           return await self._fetch("DELETE", f"/items/{key}")

        async def update(self, updates: Dict[str, Any], key: str, options: Optional[Dict] = None) -> Optional[Dict]:
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

            expires = self.calculate_expires(options.get("expireIn"), options.get("expireAt"))
                
            if expires:
                processed_updates["set"]["__expires"] = expires

            return await self._fetch("PATCH", f"/items/{key}", {"updates": processed_updates})

        async def fetch(self, query: Optional[Dict] = None, limit: Optional[int] = None, last: Optional[str] = None, 
                  options: Optional[Dict] = None) -> Dict[str, Any]:
            options = options or {}
            
            # Handle both direct parameters and options
            limit, last = limit or options.get("limit"), last or options.get("last")

            query_params = {
                "query": query,
                "limit": limit,
                "last": last
            }
            query_params = {k: v for k, v in query_params.items() if v is not None}

            if self.db.debug:
                print(f"Fetch params sent to server: {query_params}")

            response = await self._fetch("POST", "/query", query_params)
            if response:
                return {
                    "items": response.get("items", []),
                    "last": response.get("last"),
                    "count": response.get("count", 0)
                }
            return {"items": [], "last": None, "count": 0}

        async def put_many(self, items: List[Dict]) -> Optional[Dict]:
            if not isinstance(items, list) or len(items) == 0:
                raise ValueError("put_many requires a non-empty list of items")
            return await self.put(items)

    def __init__(self, api_key: str, project_id: str, debug: bool = False):
        super().__init__(api_key, project_id, debug)
        self._client = AsyncClient()