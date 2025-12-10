import pymongo
import logging
import os
import json
from datetime import datetime, timedelta
from alert import raise_ticket

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mongo_copier')

def parse_date(date_str):
    # Handle various date formats if needed, assuming ISO format from previous steps
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return datetime.now() # Fallback

def read_json_data(country, today_str, file_type):
    file_path = os.path.join(country, today_str, 'Data', f'{country}_data_{file_type}.json')
    if not os.path.exists(file_path):
        logger.warning(f"Data file not found: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert date strings to datetime objects
        for item in data:
            if 'date_of_scraping' in item and isinstance(item['date_of_scraping'], str):
                item['date_of_scraping'] = parse_date(item['date_of_scraping'])
        return data
    except Exception as e:
        logger.error(f"Error reading JSON file {file_path}: {e}")
        raise_ticket("Step 9", "read_json_data", f"Error reading JSON file {file_path}: {str(e)}", country)
        return []

def upload_to_melody(data_list, target_collection, today_str, force_upload=False):
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

        # Insert in batches
        batch = []
        for doc in data_list:
            doc.pop('_id', None)  # Avoid duplicate _id insertion
            batch.append(doc)
            if len(batch) >= BATCH_SIZE:
                target_collection.insert_many(batch, ordered=False)
                total_docs += len(batch)
                batch = []

        if batch:
            target_collection.insert_many(batch, ordered=False)
            total_docs += len(batch)

        logger.info(f"Uploaded {total_docs} documents to {target_collection.name}")
        return {'status': 'success', 'copied_count': total_docs, 'date': today_str}

    except Exception as e:
        logger.error(f"Error during upload: {e}")
        raise_ticket("Step 9", "upload_to_melody", f"Error uploading to melody: {str(e)}")
        return {'status': 'error', 'error': str(e), 'date': today_str}

def get_last_day_count(server_collection, current_date):
    pipeline = [
        {"$match": {"date_of_scraping": {"$lt": datetime.strptime(current_date, '%Y-%m-%d')}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_of_scraping"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": -1}},
        {"$limit": 1}
    ]
    result = list(server_collection.aggregate(pipeline))
    return result[0] if result else None

def check_data_existance(server_collection, today_str):
    start = datetime.strptime(today_str, '%Y-%m-%d')
    end = start.replace(hour=23, minute=59, second=59)
    count = server_collection.count_documents({"date_of_scraping": {"$gte": start, "$lte": end}})
    return count if count else None

def upload_to_data_melody(countries, today_str, config):
    
    try:
        server_client = pymongo.MongoClient(config['SERVER_URI'])
        server_db = server_client[config['DB_NAME']]
        
        logger.info("Connected to server database successfully.")
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise_ticket("Step 9", "upload_to_data_melody", f"Database connection failed: {str(e)}")
        return

    # If countries is a dict (like in master.py), we iterate keys. If list, iterate items.
    country_list = countries.keys() if isinstance(countries, dict) else countries
    
    threshold_percent = config.get('THRESHOLD_PERCENT', 10.0)

    file_type = 'footwear' if config['DB_NAME'] == 'footwear_analytics' else 'apparel'
    logger.info(f"Processing data for file type: {file_type}")

    for country in country_list:
        collection_name = f"{config['COLLECTION_PREFIX']}{country.lower()}"
        server_collection = server_db[collection_name]

        # Read data from JSON file
        data_list = read_json_data(country, today_str, file_type)
        today_count = len(data_list)

        if today_count == 0:
            logger.warning(f"{country}: No data found in JSON file for {today_str} ({file_type}). Skipping.")
            continue

        last_day_data = get_last_day_count(server_collection, today_str)
        last_count = last_day_data['count'] if last_day_data else 0
        last_date = last_day_data['_id'] if last_day_data else "N/A"

        logger.info(f"{country.upper()} | Today's count ({today_str}): {today_count} | Last count ({last_date}): {last_count}")

        # Deviation Logic
        should_proceed = True
        if last_count > 0:
            # Calculate boundaries
            lower_bound = last_count * (1 - threshold_percent / 100)
            # upper_bound = last_count * (1 + threshold_percent / 100) # Not strictly needed for logic but good for reference

            if today_count < lower_bound:
                logger.warning(f"{country}: Today's count ({today_count}) is less than {100-threshold_percent}% of previous day ({last_count}). Skipping upload.")
                raise_ticket("Step 9", "upload_to_data_melody", f"Skipped upload for {country} due to high deviation. Today: {today_count}, Last: {last_count} ({last_date})", country)
                should_proceed = False
            elif today_count > last_count * (1 + threshold_percent / 100):
                logger.info(f"{country}: Today's count ({today_count}) is greater than {100+threshold_percent}% of previous day ({last_count}). Proceeding with upload.")
                raise_ticket("Step 9", "upload_to_data_melody", f"Proceeding with upload for {country} due to high deviation. Today: {today_count}, Last: {last_count} ({last_date})", country)
                should_proceed = True
            else:
                logger.info(f"{country}: Count is within normal range.")
                should_proceed = True
        else:
            logger.info(f"{country}: No previous data found. Proceeding with upload.")
            should_proceed = True

        if should_proceed:
            server_data_count = check_data_existance(server_collection, today_str)
            force_upload = config.get('FORCE_UPLOAD', False)
            
            if server_data_count:
                if force_upload:
                    logger.info(f"Reupload enabled: Deleting existing data for {today_str} in {collection_name}...")
                    start = datetime.strptime(today_str, '%Y-%m-%d')
                    end = start.replace(hour=23, minute=59, second=59)
                    server_collection.delete_many({"date_of_scraping": {"$gte": start, "$lte": end}})
                else:
                    logger.info(f"Skipping {country.upper()} - data for {today_str} already exists in melody (FORCE_UPLOAD=False).")
                    continue

            if config.get('DRY_RUN', False):
                 logger.info(f"[DRY RUN] Would upload {today_count} documents to {collection_name}.")
            else:
                logger.info(f"Uploading {today_count} documents in chunks to {collection_name}...")
                upload_to_melody(data_list, server_collection, today_str, force_upload=force_upload)
                logger.info(f"Upload complete for {country.upper()}.")

    server_client.close()
    logger.info("Upload process completed.")

