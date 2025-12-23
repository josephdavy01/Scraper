import pymongo
import logging
from datetime import datetime, timedelta

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mongo_copier')

# ---------------------------------- CONFIG ----------------------------------

SERVER_MONGO_URI = 'replace_with_actul_server_string'  # Change to your server URI
LOCAL_MONGO_URI = 'mongodb://localhost:27017'
local_DB_NAME = 'tg_analytics'
COLLECTION_PREFIX = 'crawler_sink_on_'

today_str = datetime.now().strftime('%Y-%m-%d')
# today_str = '2025-12-05'

THRESHOLD_PERCENT = 50.0  # Don't upload if today's count differs by more than the set percentage
CHUNK_SIZE = 5000  # Number of docs per insert chunk
ALLOW_REUPLOAD = False  # Set True to delete and re-upload for the same day

# ---------------------------------- CONNECTIONS ----------------------------------

server_client = pymongo.MongoClient(SERVER_MONGO_URI)
server_db = server_client[local_DB_NAME]

local_client = pymongo.MongoClient(LOCAL_MONGO_URI)
local_db = local_client[local_DB_NAME]

# ---------------------------------- UTILITY FUNCTIONS ----------------------------------

def upload_to_melody(source_collection, target_collection, today_str, force_upload=True):
    BATCH_SIZE = 1000
    total_docs = 0

    filter_date = datetime.strptime(today_str, '%Y-%m-%d')
    next_day = filter_date + timedelta(days=1)

    try:
        if not force_upload:
            existing_count = target_collection.count_documents({
                'date_of_scraping': {'$gte': filter_date, '$lt': next_day}
            })

            if existing_count > 0:
                logger.warning(f"Data already exists for {today_str} in {target_collection.name}. Skipping upload.")
                return {
                    'status': 'skipped',
                    'reason': 'data_exists',
                    'existing_count': existing_count,
                    'date': today_str
                }

        cursor = source_collection.find({
            'date_of_scraping': {'$gte': filter_date, '$lt': next_day}
        }).batch_size(BATCH_SIZE)

        batch = []
        for doc in cursor:
            doc.pop('_id', None)  # Avoid duplicate _id insertion
            batch.append(doc)
            if len(batch) >= BATCH_SIZE:
                target_collection.insert_many(batch, ordered=False)
                total_docs += len(batch)
                batch = []

        if batch:
            target_collection.insert_many(batch, ordered=False)
            total_docs += len(batch)

        logger.info(f"Copied {total_docs} documents to {target_collection.name}")
        return {'status': 'success', 'copied_count': total_docs, 'date': today_str}

    except Exception as e:
        logger.error(f"Error during upload: {e}")
        return {'status': 'error', 'error': str(e), 'date': today_str}

def get_previous_days(server_collection, current_date, num_days=5):
    pipeline = [
        {"$match": {"date_of_scraping": {"$lt": datetime.strptime(current_date, '%Y-%m-%d')}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_of_scraping"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": -1}},
        {"$limit": num_days}
    ]
    return list(server_collection.aggregate(pipeline))

def get_today_count(local_collection, today_str):
    # Convert the date to the MongoDB format
    db_date = datetime.strptime(today_str, '%Y-%m-%d')

    pipeline = [
        {"$match": {"date_of_scraping": db_date}},
        {"$count": "count"}
    ]
    result = list(local_collection.aggregate(pipeline))
    return result[0]['count'] if result else 0

def should_upload(today_count, previous_counts):
    if len(previous_counts) < 3:
        return True
    mean_count = sum([d['count'] for d in previous_counts]) / len(previous_counts)
    deviation = abs(today_count - mean_count) / mean_count * 100
    return deviation <= THRESHOLD_PERCENT

def check_data_existance(server_collection, today_str):
    start = datetime.strptime(today_str, '%Y-%m-%d')
    end = start.replace(hour=23, minute=59, second=59)
    count = server_collection.count_documents({"date_of_scraping": {"$gte": start, "$lte": end}})
    if count:
        return count
    else:
        return None

# ---------------------------------- MAIN LOGIC ----------------------------------

day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')
active_countries = ['uae', 'uk', 'usa']

for country in active_countries:
    local_collection_name = f"{COLLECTION_PREFIX}{country}"
    server_collection_name = f"{COLLECTION_PREFIX}{country}"
    server_collection = server_db[server_collection_name]
    local_collection = local_db[local_collection_name]

    today_count = get_today_count(local_collection, today_str)
    if today_count == 0:
        continue

    previous_counts = get_previous_days(server_collection, today_str, 5)

    logging.info(f"{country.upper()} | Today's count: {today_count} | Historical mean: {round(sum([x['count'] for x in previous_counts])/len(previous_counts), 2) if previous_counts else 'N/A'}")

    server_data_count = check_data_existance(server_collection, today_str)
    if server_data_count:
        if server_data_count == today_count:
            logging.info(f"Skipping {country.upper()} - data for {today_str} already exists in melody.")
            continue
        else:
            logging.info(f"Reupload enabled: Deleting existing data for {today_str} in {local_collection_name}...")
            start = datetime.strptime(today_str, '%Y-%m-%d')
            end = start.replace(hour=23, minute=59, second=59)
            server_collection.delete_many({"date_of_scraping": {"$gte": start, "$lte": end}})

    if should_upload(today_count, previous_counts):
        logging.info(f"Uploading {today_count} documents in chunks to {local_collection_name}...")
        upload_to_melody(local_collection, server_collection, today_str)
        logging.info(f"Upload complete for {country.upper()}.")
    else:
        logging.info(f"Skipping upload for {country.upper()} due to >{THRESHOLD_PERCENT}% deviation.")

server_client.close()
local_client.close()
logging.info("Bulk upload with validation completed.")
