# bulk_upload_check.py
# Compares today's JSON data count with the mean of the last 5 days in the server DB for each country
# Uploads data to local MongoDB only if count deviation is within threshold
# Supports chunked upload and re-upload toggle

import os
import json
from datetime import datetime
import pymongo
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
COUNTRIES = {
    'Canada': 'https://shop.lululemon.com/en-ca/',
    'USA': 'https://shop.lululemon.com/'
}
# ---------------------------------- CONFIG ----------------------------------

SERVER_MONGO_URI = os.getenv('MONGO_SERVER_URI')
LOCAL_MONGO_URI = os.getenv('MONGO_LOCAL_URI')
DB_NAME = 'tg_analytics'
COLLECTION_PREFIX = 'crawler_sink_lululemon_'

FETCH_DATE = datetime.now().strftime('%Y-%m-%d')
# FETCH_DATE = '2025-12-09'
# 
THRESHOLD_PERCENT = 50.0  # Don't upload if today's count differs by more than the set percentage
CHUNK_SIZE = 5000  # Number of docs per insert chunk

# ---------------------------------- CONNECTIONS ----------------------------------

server_client = pymongo.MongoClient(SERVER_MONGO_URI)
server_db = server_client[DB_NAME]

local_client = pymongo.MongoClient(LOCAL_MONGO_URI)
local_db = local_client[DB_NAME]

# ---------------------------------- UTILITY FUNCTIONS ----------------------------------

def get_previous_days(server_collection, current_date, num_days=5):
    pipeline = [
        {"$match": {"date_of_scraping": {"$lt": datetime.strptime(current_date, '%Y-%m-%d')}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_of_scraping"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": -1}},
        {"$limit": num_days}
    ]
    return list(server_collection.aggregate(pipeline))

def get_today_json_count(country, fetch_date):
    path = os.path.join(country, fetch_date, 'Data', f"products_data_deduped_{country}.json")
    if not os.path.exists(path):
        print(f"JSON file not found: {path}")
        return 0, []
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return len(data), data

def should_upload(today_count, previous_counts):
    if len(previous_counts) < 3:
        return True
    mean_count = sum([d['count'] for d in previous_counts]) / len(previous_counts)
    deviation = abs(today_count - mean_count) / mean_count * 100
    return deviation <= THRESHOLD_PERCENT

def already_uploaded_today(local_collection, fetch_date):
    start = datetime.strptime(fetch_date, '%Y-%m-%d')
    end = start.replace(hour=23, minute=59, second=59)
    return local_collection.count_documents({"date_of_scraping": {"$gte": start, "$lte": end}}) > 0

def upload_in_chunks(collection, data):
    for i in range(0, len(data), CHUNK_SIZE):
        chunk = data[i:i+CHUNK_SIZE]
        collection.insert_many(chunk)

# ---------------------------------- MAIN LOGIC ----------------------------------

def load_to_db(coutries, fetch_date, allow_reupload=False):
    for country in coutries.keys():
        collection_name = f"{COLLECTION_PREFIX}{country.lower()}"
        server_collection = server_db[collection_name]
        local_collection = local_db[collection_name]

        today_count, json_data = get_today_json_count(country, fetch_date)
        if today_count == 0:
            continue

        previous_counts = get_previous_days(server_collection, fetch_date, 5)

        print(f"\n{country.upper()} | Today's count: {today_count} | Historical mean: {round(sum([x['count'] for x in previous_counts])/len(previous_counts), 2) if previous_counts else 'N/A'}")

        for doc in json_data:
            if isinstance(doc['date_of_scraping'], str):
                try:
                    doc['date_of_scraping'] = datetime.strptime(doc['date_of_scraping'], '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    doc['date_of_scraping'] = datetime.strptime(doc['date_of_scraping'], '%Y-%m-%d %H:%M:%S')


        if collection_name not in local_db.list_collection_names():
            local_db.create_collection(collection_name)

        if already_uploaded_today(local_collection, fetch_date):
            if allow_reupload:
                print(f"Reupload enabled: Deleting existing data for {fetch_date} in {collection_name}...")
                start = datetime.strptime(fetch_date, '%Y-%m-%d')
                end = start.replace(hour=23, minute=59, second=59)
                local_collection.delete_many({"date_of_scraping": {"$gte": start, "$lte": end}})
            else:
                print(f"Skipping {country.upper()} - data for {fetch_date} already exists in local DB.")
                continue

        if should_upload(today_count, previous_counts):
            print(f"Uploading {today_count} documents in chunks to {collection_name}...")
            upload_in_chunks(local_collection, json_data)
            print(f"Upload complete for {country.upper()}.")
        else:
            print(f"Skipping upload for {country.upper()} due to >{THRESHOLD_PERCENT}% deviation.")
    
    server_client.close()
    local_client.close()
    print("\nBulk upload with validation completed.")

if __name__ == "__main__":
    load_to_db(COUNTRIES, FETCH_DATE, allow_reupload=False)
    server_client.close()
    local_client.close()