import os
from pymongo import MongoClient
from datetime import date, datetime


def parse_launch_date(date_string):
    try:
        return datetime.strptime(date_string, '%Y-%m-%d')
    except ValueError:
        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except:
            print(f"Warning: Could not parse date '{date_string}', using today")
            return datetime.strptime(date.today().strftime('%Y-%m-%d'), '%Y-%m-%d')


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
    
    print(f"Removed {sum(len(item['ids']) - 1 for item in duplicates)} duplicate SKUs for {collection_name} on {date}.")

if __name__ == "__main__":
    connection_string = "mongodb://localhost:27017"
    database_name = 'tg_analytics' 
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-06'
   
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')
    
    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = ['INDIA']
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = ['UAE', 'UK']
    else:
        countries = []
    
    for country in countries:
        collections = [f'crawler_sink_puma_{country.lower()}', f'crawler_sink_puma_{country.lower()}_footwear',f'crawler_sink_puma_{country.lower()}_kids']
        
        for collection_name in collections:
            remove_duplicate_skus(connection_string, database_name, collection_name, country, today_str)