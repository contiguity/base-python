from contiguity_base import connect

# Initialize the Contiguity client
db = connect("api-key", "project-id")

# Create a Base instance
my_base = db.Base("randomBase9000")

# Helper function to print results
def print_result(operation, result):
    print(f"{operation} result: {result}")
    if result is None:
        print(f"Warning: {operation} operation failed!")

# Put an item with a specific key
result1 = my_base.put({"value": "Hello world!"}, "my-key-py")
print_result("Put", result1)

# Insert an item with a specific key
result2 = my_base.insert({"name": "John Doe", "age": 30}, "john-doe-py")
print_result("Insert", result2)

# Insert an item with a specific key and expireIn
result3 = my_base.insert({"name": "Jane Doe", "age": 28}, "jane-doe-py", expire_in=3600)
print_result("Insert with expireIn", result3)

# Get an item
get_result = my_base.get("john-doe-py")
print_result("Get", get_result)

# Update an item
update_result = my_base.update({"age": 31}, "john-doe-py")
print_result("Update", update_result)

# Fetch items
try:
    fetch_result = my_base.fetch({"age": {"$gt": 25}}, limit=10)
    print_result("Fetch", fetch_result)
except Exception as e:
    print(f"Fetch operation failed: {str(e)}")

# Delete an item
delete_result = my_base.delete("jane-doe-py")
print_result("Delete", delete_result)