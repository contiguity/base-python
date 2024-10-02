from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from httpx import AsyncClient, Client


class BaseContiguity(ABC):
    """"""
    _client = Union[AsyncClient, Client]
    base_url = "https://api.base.contiguity.co/v1"

    class Util:
        """"""
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
        
    class Base(ABC):
        """"""
        def __init__(self, db: "BaseContiguity", name: str):
            self.db = db
            self.name = name
            self.util = db.Util

        @abstractmethod
        def _fetch(self, method: str, path: str, body: Optional[Dict] = None) -> Optional[Dict]:
            """"""

        @abstractmethod
        def put(self, items: Union[Dict, List[Dict]], key: Optional[str] = None, expire_in: Optional[int] = None, expire_at: Optional[Union[datetime, str]] = None, options: Optional[Dict] = None) -> Optional[Dict]:
            """"""

        @abstractmethod
        def insert(self, data: Dict, key: Optional[str] = None, expire_in: Optional[int] = None, expire_at: Optional[Union[datetime, str]] = None, options: Optional[Dict] = None) -> Optional[Dict]:
            """"""

        @abstractmethod
        def get(self, key: str) -> Optional[Dict]:
            """"""

        @abstractmethod
        def delete(self, key: str) -> Optional[Dict]:
            """"""

        @abstractmethod
        def update(self, updates: Dict[str, Any], key: str, options: Optional[Dict] = None) -> Optional[Dict]:
            """"""

        @abstractmethod
        def fetch(self, query: Optional[Dict] = None, limit: Optional[int] = None, last: Optional[str] = None, options: Optional[Dict] = None) -> Dict[str, Any]:
            """"""

        @abstractmethod
        def put_many(self, items: List[Dict]) -> Optional[Dict]:
            """"""

        @staticmethod
        def get_expire(expire_in: Optional[int], expire_at: Optional[Union[datetime, str]], options: Optional[Dict]) -> Tuple[int]:
            return expire_in or options.get("expireIn"), expire_at or options.get("expireAt")
        
        @staticmethod
        def calculate_expires(expire_in: Optional[int], expire_at: Optional[Union[datetime, str]]) -> Optional[int]:
            """"""
            if expire_at:
                if isinstance(expire_at, datetime):
                    return int(expire_at.timestamp())
                else:
                    return int(datetime.fromisoformat(expire_at).timestamp())
            elif expire_in:
                return int(datetime.now().timestamp()) + expire_in
            return None

    def __init__(self, api_key: str, project_id: str, debug: bool = False) -> None:
        self.api_key = api_key
        self.project_id = project_id
        self.debug = debug


    def connect_to_base(self, name: str) -> Base:
        """"""
        return self.Base(self, name)
