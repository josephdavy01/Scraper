from pymongo import MongoClient
from datetime import date, datetime
from pymongo.write_concern import WriteConcern

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

# MongoDB connection details
connection_string = "mongodb://localhost:27017"
database_name = 'tg_analytics'

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')
#today_str = '2025-09-25'

# Get current datetime and weekday name
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

if day in ['Monday','Tuesday','Wednesday', 'Thursday','Friday', 'Saturday']:
    countries = ['India', 'UK']
else:
    countries = []

# Connect to MongoDB
client = MongoClient(connection_string)
db = client[database_name]

for country in countries:
    collections = [f'crawler_sink_h&m_{country.lower()}', f'crawler_sink_h&m_{country.lower()}_kids']
    for collection_name in collections:
        collection = db[collection_name]

        # Ensure index for faster lookups
        collection.create_index([("date_of_scraping", 1), ("color_id", 1)])

        target_date = parse_launch_date(today_str)

        pipeline = [
            {"$match": {"date_of_scraping": target_date}},
            {"$group": {
                "_id": {"date_of_scraping": "$date_of_scraping", "color_id": "$color_id"},
                "availabilities": {"$addToSet": "$availability"}
            }}
        ]

        bulk_delete_entries = [
            {"date_of_scraping": res["_id"]["date_of_scraping"], "color_id": res["_id"]["color_id"]}
            for res in collection.aggregate(pipeline) if set(res["availabilities"]) == {"out_of_stock"}
        ]

        if bulk_delete_entries:
            print(f'Deleting {len(bulk_delete_entries)} color_ids from {collection_name}')
            
            batch_size = 1000
            for i in range(0, len(bulk_delete_entries), batch_size):
                batch = bulk_delete_entries[i:i+batch_size]
                delete_query = {
                    "date_of_scraping": target_date, 
                    "color_id": {"$in": [entry["color_id"] for entry in batch]}
                }
                delete_result = collection.with_options(write_concern=WriteConcern("majority", wtimeout=1000)).delete_many(delete_query)
                print(f'Deleted {delete_result.deleted_count} documents in batch {i//batch_size + 1}')
        else:
            print(f'No Out of Stock data found for {country}_{today_str}')

client.close()