from contiguity_base import connect

# Initialize the Contiguity client
db = connect("613cb117eeff3a6ab7513521568521823e5c73f32344c00d000023854b085911", "c10067935b18ef6d4f4c83f8cde3c59a")

# Create a Base instance
my_base = db.Base("randomBase9000")

# Helper function to print results
def print_result(operation, result):
    print(f"{operation} result: {result}")
    if result is None:
        print(f"Warning: {operation} operation failed!")

# Put an item with a specific key
result1 = my_base.put({"value": "Hello world!"}, "my-key-py2")
print_result("Put", result1)

# Insert an item with a specific key
result2 = my_base.insert({"name": "John Doe", "age": 30}, "john-doe-py2")
print_result("Insert", result2)

# Insert an item with a specific key and expireIn
result3 = my_base.insert({"name": "Jane Doe", "age": 28}, "jane-doe-pyyyyyyy2", expire_in=3600)
print_result("Insert with expireIn", result3)

# Get an item
get_result = my_base.get("john-doe-py2")
print_result("Get", get_result)

# Update an item
update_result = my_base.update({"age": 31}, "john-doe-py2")
print_result("Update", update_result)

# Fetch items with a query
fetch_result1 = my_base.fetch({"age?gte": 25}, limit=10)
print_result("Fetch with query", fetch_result1)

# Fetch items with an empty query
fetch_result2 = my_base.fetch({})
print_result("Fetch with empty query", fetch_result2)

# Fetch items without any arguments
fetch_result3 = my_base.fetch()
print_result("Fetch without arguments", fetch_result3)

# Delete an item
delete_result = my_base.delete("jane-doe-py2")
print_result("Delete", delete_result)