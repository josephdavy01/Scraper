import pymongo
import logging
from datetime import datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------- UTILITY FUNCTIONS ----------------------------------

def _upload_chunk(source_collection, target_collection, date_filter):
    """Helper function to upload documents in chunks."""
    BATCH_SIZE = 1000
    total_docs = 0
    cursor = source_collection.find(date_filter).batch_size(BATCH_SIZE)
    
    batch = []
    for doc in cursor:
        doc.pop('_id', None)  # Avoid duplicate _id insertion
        batch.append(doc)
        if len(batch) >= BATCH_SIZE:
            target_collection.insert_many(batch, ordered=False)
            total_docs += len(batch)
            logger.info(f"  ... inserted {total_docs} documents")
            batch = []
    
    if batch:
        target_collection.insert_many(batch, ordered=False)
        total_docs += len(batch)
        
    return total_docs

def _get_previous_days_counts(server_collection, current_date, num_days=5):
    """Gets the document counts for the previous N days."""
    pipeline = [
        {"$match": {"date_of_scraping": {"$lt": datetime.strptime(current_date, '%Y-%m-%d')}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_of_scraping"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": -1}},
        {"$limit": num_days}
    ]
    return list(server_collection.aggregate(pipeline))

def _get_today_count(local_collection, today_date_str):
    """Gets the document count for the specified day."""
    db_date = datetime.strptime(today_date_str, '%Y-%m-%d')
    return local_collection.count_documents({"date_of_scraping": db_date})

def _should_upload(today_count, previous_counts, threshold_percent):
    """Determines if the count deviation is within the acceptable threshold."""
    if not previous_counts or len(previous_counts) < 3:
        logger.info("Not enough historical data to check deviation. Proceeding with upload check.")
        return True
    
    mean_count = sum(d['count'] for d in previous_counts) / len(previous_counts)
    if mean_count == 0:
        logger.warning("Historical mean is 0. Allowing upload.")
        return True
        
    deviation = abs(today_count - mean_count) / mean_count * 100
    logger.info(f"Deviation from historical mean is {deviation:.2f}%.")
    return deviation <= threshold_percent

# ---------------------------------- MAIN LOGIC ----------------------------------

def upload_data_to_melody_footwear(country_config, mongo_config, today_date_str):
    """
    Connects to MongoDB to upload data, supporting dry run and force upload flags.
    """
    # Extract flags from the config, defaulting to False if they don't exist
    dry_run = mongo_config.get('DRY_RUN', False)
    force_upload = mongo_config.get('FORCE_UPLOAD', False)

    try:
        server_client = pymongo.MongoClient(mongo_config['SERVER_URI'])
        local_client = pymongo.MongoClient(mongo_config['LOCAL_URI'])
        server_db = server_client[mongo_config['DB_NAME']]
        local_db = local_client[mongo_config['DB_NAME']]
        logger.info("Successfully connected to local and server MongoDB.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return

    active_countries = country_config.keys()
    start_date = datetime.strptime(today_date_str, '%Y-%m-%d')
    date_filter = {"date_of_scraping": start_date}

    for country in active_countries:
        collection_name = f"{mongo_config['COLLECTION_PREFIX']}{country.lower()}"
        server_collection = server_db[collection_name]
        local_collection = local_db[collection_name]
        
        logger.info(f"--- Processing country: {country.upper()} ---")

        today_count = _get_today_count(local_collection, today_date_str)
        if today_count == 0:
            logger.warning(f"No documents found for {today_date_str} in local collection {collection_name}. Skipping.")
            continue

        previous_counts = _get_previous_days_counts(server_collection, today_date_str)
        mean_count = round(sum(d['count'] for d in previous_counts) / len(previous_counts), 2) if previous_counts else 'N/A'
        logger.info(f"Local count for today: {today_count} | Historical mean on server: {mean_count}")

        # Check for existing data on the server
        server_data_count = server_collection.count_documents(date_filter)
        if server_data_count > 0:
            logger.warning(f"Data for {today_date_str} already exists on server ({server_data_count} docs).")
            if force_upload:
                logger.info("FORCE_UPLOAD is True. Deleting existing data.")
                if not dry_run:
                    result = server_collection.delete_many(date_filter)
                    logger.info(f"Deleted {result.deleted_count} documents from server collection.")
                else:
                    logger.info(f"[DRY RUN] Would delete {server_data_count} documents from {collection_name}.")
            else:
                logger.info("FORCE_UPLOAD is False. Skipping upload for this country.")
                continue # Move to the next country

        # Proceed with upload if deviation is acceptable
        if _should_upload(today_count, previous_counts, mongo_config['THRESHOLD_PERCENT']):
            if dry_run:
                logger.info(f"[DRY RUN] Would upload {today_count} documents to {collection_name}.")
            else:
                logger.info(f"Uploading {today_count} documents to {collection_name}...")
                try:
                    copied_docs = _upload_chunk(local_collection, server_collection, date_filter)
                    logger.info(f"Upload complete for {country.upper()}. Copied {copied_docs} documents.")
                except Exception as e:
                    logger.error(f"An error occurred during upload for {country.upper()}: {e}")
        else:
            logger.warning(f"Skipping upload for {country.upper()} due to >{mongo_config['THRESHOLD_PERCENT']}% deviation from mean.")

    server_client.close()
    local_client.close()
    logger.info("--- Melody upload process finished. ---")