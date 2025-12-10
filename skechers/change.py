# from pymongo import MongoClient

# # connect to MongoDB
# client = MongoClient("mongodb://localhost:27017/")  # update your connection string if needed
# db = client["tg_analytics"]
# collection = db["crawler_sink_skechers_usa_footwear"]

# # update all documents where agegroup == "Adult"
# result = collection.update_many(
#     {"age_group": "Adult"},
#     {"$set": {"age_group": "adult"}}
# )

# print(f"Matched: {result.matched_count}, Modified: {result.modified_count}")

from pymongo import MongoClient

# connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")

db = client["tg_analytics"]
collection = db["crawler_sink_skechers_usa_footwear"]

result = collection.update_many(
    {"age_group": {"$type": "string"}},
    [{"$set": {"age_group": ["$age_group"]}}]  # wrap the value inside an array
)

print(f"Matched documents: {result.matched_count}")
print(f"Modified documents: {result.modified_count}")

