from pymongo import MongoClient
from datetime import date, datetime

def parse_launch_date(date_string):
    format_string_with_ms = '%Y-%m-%dT%H:%M:%S.%fZ'
    format_string_without_ms = '%Y-%m-%dT%H:%M:%SZ'
    format_string_date_only = '%Y-%m-%d'
    format_string_with_ms_no_tz = '%Y-%m-%d %H:%M:%S.%f'
    
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            try:
                return datetime.strptime(date_string, format_string_date_only)
            except ValueError:
                return datetime.strptime(date_string, format_string_with_ms_no_tz)

def remove_duplicate_skus(connection_string, database_name, collection_name, geography, date):
    # Connect to MongoDB
    client = MongoClient(connection_string)
    db = client[database_name]
    collection = db[collection_name]
    
    # Convert the date to the MongoDB format
    db_date = parse_launch_date(date)
    
    # Define the match criteria
    match_criteria = {
        "date_of_scraping": db_date
    }
    
    # Aggregate to find duplicate SKUs
    pipeline = [
        {"$match": match_criteria},
        {"$group": {
            "_id": "$sku",
            "count": {"$sum": 1},
            "ids": {"$push": "$_id"}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]
    
    duplicates = list(collection.aggregate(pipeline))
    
    # Remove duplicates
    for item in duplicates:
        ids = item['ids']
        # Keep the first document, remove the rest
        ids_to_remove = ids[1:]
        collection.delete_many({"_id": {"$in": ids_to_remove}})
    
    print(f"Removed {sum(len(item['ids']) - 1 for item in duplicates)} duplicate SKUs for {geography} on {date}.")

# Example usage
connection_string = "mongodb://localhost:27017"
database_name = 'tg_analytics'

today = date.today()
today_str = today.strftime('%Y-%m-%d')
# today_str = '2025-12-06'

country = 'India'

geography = country.lower()
collection_name = f'crawler_sink_uspolo_{geography}'

remove_duplicate_skus(connection_string, database_name, collection_name, geography, today_str)