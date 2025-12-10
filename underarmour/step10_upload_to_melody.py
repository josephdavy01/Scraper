import pymongo
import logging
from datetime import datetime, timedelta

# ---------------------------------- LOGGING CONFIG ----------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mongo_copier')

# ---------------------------------- CONFIG ----------------------------------

SERVER_MONGO_URI = 'mongodb://root:iK&dsCaTio976fghI*(bgdskk)~@34.143.153.196:28018/tg_analytics?authSource=admin'
LOCAL_MONGO_URI = 'mongodb://localhost:27017'
DB_NAME = 'tg_analytics'
COLLECTION_PREFIX = 'crawler_sink_underarmour_'

MON_WED_FRI = ['india', 'uae']
TUE_THU_SAT = ['uk', 'usa']

today_str = datetime.now().strftime('%Y-%m-%d')
# today_str = '2025-11-27'
THRESHOLD_PERCENT = 25  # Upload only if today's count is within ±100% of mean
CHUNK_SIZE = 5000
ALLOW_REUPLOAD = True  # Change to True to force re-upload if data already exists

# ---------------------------------- CONNECTIONS ----------------------------------

server_client = pymongo.MongoClient(SERVER_MONGO_URI)
server_db = server_client[DB_NAME]

local_client = pymongo.MongoClient(LOCAL_MONGO_URI)
local_db = local_client[DB_NAME]

# ---------------------------------- UTILITY FUNCTIONS ----------------------------------

def upload_to_melody(source_collection, target_collection, today_str):
    BATCH_SIZE = 1000
    total_docs = 0

    filter_date = datetime.strptime(today_str, '%Y-%m-%d')
    next_day = filter_date + timedelta(days=1)

    try:
        cursor = source_collection.find({
            'date_of_scraping': {'$gte': filter_date, '$lt': next_day}
        }).batch_size(BATCH_SIZE)

        batch = []
        for doc in cursor:
            doc.pop('_id', None)
            batch.append(doc)
            if len(batch) >= BATCH_SIZE:
                target_collection.insert_many(batch, ordered=False)
                total_docs += len(batch)
                batch = []

        if batch:
            target_collection.insert_many(batch, ordered=False)
            total_docs += len(batch)

        logger.info(f" Copied {total_docs} documents to {target_collection.name}")
        return {'status': 'success', 'copied_count': total_docs, 'date': today_str}

    except Exception as e:
        logger.error(f" Error during upload: {e}")
        return {'status': 'error', 'error': str(e), 'date': today_str}

def get_previous_days(server_collection, current_date, num_days=5):
    pipeline = [
        {"$match": {"date_of_scraping": {"$lt": datetime.strptime(current_date, '%Y-%m-%d')}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_of_scraping"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": -1}},
        {"$limit": num_days}
    ]
    return list(server_collection.aggregate(pipeline))

def get_today_count(local_collection, today_str):
    start = datetime.strptime(today_str, '%Y-%m-%d')
    end = start + timedelta(days=1)

    pipeline = [
        {"$match": {"date_of_scraping": {"$gte": start, "$lt": end}}},
        {"$count": "count"}
    ]
    result = list(local_collection.aggregate(pipeline))
    return result[0]['count'] if result else 0

def should_upload(today_count, previous_counts):
    if len(previous_counts) < 3:
        logger.info(" Not enough historical data (<3). Allowing upload.")
        return True

    mean_count = sum([d['count'] for d in previous_counts]) / len(previous_counts)
    if mean_count == 0:
        logger.info(" Historical mean is 0. Allowing upload to avoid divide-by-zero.")
        return True

    deviation = abs(today_count - mean_count) / mean_count * 100
    logger.info(f" Deviation from mean: {round(deviation, 2)}% (Threshold: {THRESHOLD_PERCENT}%)")
    return deviation <= THRESHOLD_PERCENT

def check_data_existence(server_collection, today_str):
    start = datetime.strptime(today_str, '%Y-%m-%d')
    end = start + timedelta(days=1)
    return server_collection.count_documents({"date_of_scraping": {"$gte": start, "$lt": end}})

# ---------------------------------- MAIN LOGIC ----------------------------------

day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')
active_countries = MON_WED_FRI if day in ['Monday', 'Wednesday', 'Friday'] else TUE_THU_SAT

for country in active_countries:
    collection_name = f"{COLLECTION_PREFIX}{country}"
    server_collection = server_db[collection_name]
    local_collection = local_db[collection_name]

    today_count = get_today_count(local_collection, today_str)
    if today_count == 0:
        logger.info(f" {country.upper()} | No local data found for {today_str}. Skipping.")
        continue

    previous_counts = get_previous_days(server_collection, today_str, 5)
    historical_mean = round(sum([x['count'] for x in previous_counts]) / len(previous_counts), 2) if previous_counts else 'N/A'

    logger.info(f"{country.upper()} | Today's count: {today_count} | Historical mean: {historical_mean}")

    server_data_count = check_data_existence(server_collection, today_str)
    if server_data_count:
        if server_data_count == today_count and not ALLOW_REUPLOAD:
            logger.info(f"Skipping {country.upper()} - identical data already exists.")
            continue
        elif not ALLOW_REUPLOAD:
            logger.info(f" Skipping {country.upper()} - data exists and reupload is disabled.")
            continue
        else:
            logger.info(f"Reupload enabled: Deleting existing data for {today_str}...")
            server_collection.delete_many({"date_of_scraping": {"$gte": datetime.strptime(today_str, '%Y-%m-%d'), "$lt": datetime.strptime(today_str, '%Y-%m-%d') + timedelta(days=1)}})

    if should_upload(today_count, previous_counts):
        logger.info(f" Uploading {today_count} documents to {collection_name}...")
        upload_to_melody(local_collection, server_collection, today_str)
        logger.info(f" Upload complete for {country.upper()}.")
    else:
        logger.info(f" Skipping upload for {country.upper()} due to >{THRESHOLD_PERCENT}% deviation.")

# ---------------------------------- CLEANUP ----------------------------------

server_client.close()
local_client.close()
logger.info(" Bulk upload with validation completed.")
