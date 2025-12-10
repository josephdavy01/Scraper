from pymongo import MongoClient

# Connect to local MongoDB (default port 27017)
client = MongoClient("mongodb://localhost:27017/")

# Select your database and collection
db = client["tg_analytics"]
collection = db["crawler_sink_lewkin_south_korea"]

# Update all documents where gender is "men"
result = collection.update_many(
    {"gender": "men"},         # filter
    {"$set": {"gender": "male"}}  # update operation
)

print(f"Matched {result.matched_count} documents.")
print(f"Modified {result.modified_count} documents.")
