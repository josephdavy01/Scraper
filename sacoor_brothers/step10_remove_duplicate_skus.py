import logging
from pymongo import MongoClient
from datetime import date, datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_launch_date(date_string):
    format_string_with_ms = '%Y-%m-%dT%H:%M:%S.%fZ'
    format_string_without_ms = '%Y-%m-%dT%H:%M:%SZ'
    format_string_date_only = '%Y-%m-%d'
    format_string_with_ms_no_tz = '%Y-%m-%d %H:%M:%S.%f'
    
    for fmt in [format_string_with_ms, format_string_without_ms, format_string_date_only, format_string_with_ms_no_tz]:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    raise ValueError(f"Date format for '{date_string}' not recognized.")

def remove_duplicate_skus(connection_string, database_name, collection_name, geography, date):
    try:
        client = MongoClient(connection_string)
        db = client[database_name]
        collection = db[collection_name]

        db_date = parse_launch_date(date)

        pipeline = [
            {"$match": {"date_of_scraping": db_date}},
            {"$group": {
                "_id": "$sku",
                "count": {"$sum": 1},
                "ids": {"$push": "$_id"}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]

        duplicates = list(collection.aggregate(pipeline))

        for item in duplicates:
            ids_to_remove = item['ids'][1:]  # Keep the first
            collection.delete_many({"_id": {"$in": ids_to_remove}})

        removed_count = sum(len(item['ids']) - 1 for item in duplicates)
        logging.info(f"Removed {removed_count} duplicate SKUs for {geography} on {date}.")
    except Exception as e:
        logging.error(f"Error processing {geography}: {e}")

if __name__ == "__main__":
    # Main script
    connection_string = "mongodb://localhost:27017"
    database_name = 'tg_analytics'

    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')


    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = ['UAE']
        for country in countries:
            geography = country.lower()
            collection_name = f'crawler_sink_sacoor_brothers_{geography}'
            remove_duplicate_skus(connection_string, database_name, collection_name, geography, today_str)
    else:
        logging.info(f"Today is {day}. Script only runs on Monday, Wednesday, and Friday.")

    
