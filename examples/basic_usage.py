# ruff: noqa: T201, BLE001, ANN401
from typing import Any

from contiguity_base import Base

# Create a Base instance
db = Base("randomBase9000")


# Helper function to print results
def print_result(operation: str, result: Any) -> None:
    print(f"{operation} result: {result}")
    if result is None:
        print(f"Warning: {operation} operation failed!")


# Put an item with a specific key
result1 = db.put({"key": "my-key-py", "value": "Hello world!"})
print_result("Put", result1)

# Insert an item with a specific key
result2 = db.insert({"key": "john-doe-py", "name": "John Doe", "age": 30})
print_result("Insert", result2)

# Insert an item with a specific key and expireIn
result3 = db.insert({"key": "jane-doe-py", "name": "Jane Doe", "age": 28}, expire_in=3600)
print_result("Insert with expireIn", result3)

# Get an item
get_result = db.get("john-doe-py")
print_result("Get", get_result)

# Update an item
update_result = db.update({"age": 31}, key="john-doe-py")
print_result("Update", update_result)

# Fetch items
try:
    fetch_result = db.fetch({"age": {"$gt": 25}}, limit=10)
    print_result("Fetch", fetch_result)
except Exception as exc:
    print(f"Fetch operation failed: {exc}")

# Delete an item
delete_result = db.delete("jane-doe-py")

# Delete everything
for item in db.fetch().items:
    db.delete(str(item["key"]))
