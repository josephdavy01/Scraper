import os
from pymongo import MongoClient  # type: ignore
from datetime import datetime, timedelta
from dotenv import load_dotenv  # type: ignore
from typing import List
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('mongo_copier')


def copy_mongo_collections(
    source_collections: List[str],
    target_collection: str,
    scrape_date: str,
    batch_size: int = None,
    force_upload: bool = False,
    dry_run: bool = False
):
    """
    Copy documents from source to target collections with date filtering

    Args:
        source_collections: List of source collection names (format: 'db.collection')
        target_collection: Target collection name (format: 'db.collection')
        scrape_date: Date string in YYYY-MM-DD format to filter documents
        batch_size: Optional batch size for inserts
        force_upload: If True, delete existing data for the date before upload
        dry_run: If True, simulate actions without modifying the database
    """

    # Get configuration from environment
    LOCAL_URI = os.getenv('MONGO_LOCAL_URI')
    SERVER_URI = os.getenv('MONGO_SERVER_URI')
    BATCH_SIZE = batch_size or int(os.getenv('MONGO_BATCH_SIZE', 1000))

    # Validate inputs
    if not all('.' in coll for coll in [*source_collections, target_collection]):
        raise ValueError("Collection names must be in 'db.collection' format")

    try:
        # Connect to databases
        local_client = MongoClient(LOCAL_URI)
        server_client = MongoClient(SERVER_URI)

        # Parse target
        target_db, target_coll_name = target_collection.split('.')
        target_coll = server_client[target_db][target_coll_name]

        # Parse date filter
        filter_date = datetime.strptime(scrape_date, '%Y-%m-%d')
        next_day = filter_date + timedelta(days=1)

        # Check existing documents
        existing_count = target_coll.count_documents({
            'date_of_scraping': {
                '$gte': filter_date,
                '$lt': next_day
            }
        })

        if existing_count > 0:
            if force_upload:
                logger.warning(f"{'[DRY RUN] ' if dry_run else ''}Force upload enabled. {existing_count} existing documents found in {target_collection} for {scrape_date}. Will be deleted.")
                if not dry_run:
                    delete_result = target_coll.delete_many({
                        'date_of_scraping': {
                            '$gte': filter_date,
                            '$lt': next_day
                        }
                    })
                    logger.info(f"Deleted {delete_result.deleted_count} documents.")
            else:
                logger.warning(f"Data already exists for {scrape_date} in {target_collection}")
                logger.warning(f"Found {existing_count} existing documents. Skipping upload.")
                logger.warning("Use force_upload=True to override this check")
                return {
                    'status': 'skipped',
                    'reason': 'data_exists',
                    'existing_count': existing_count,
                    'date': scrape_date,
                    'dry_run': dry_run
                }

        total_docs = 0

        # Process each source collection
        for source in source_collections:
            src_db, src_coll = source.split('.')
            collection = local_client[src_db][src_coll]

            # Count matching documents
            count = collection.count_documents({
                'date_of_scraping': {
                    '$gte': filter_date,
                    '$lt': next_day
                }
            })
            total_docs += count

            logger.info(f"{'[DRY RUN] ' if dry_run else ''}Copying {count} documents from {source} to {target_collection}")

            # Fetch documents in batches
            cursor = collection.find({
                'date_of_scraping': {
                    '$gte': filter_date,
                    '$lt': next_day
                }
            }).batch_size(BATCH_SIZE)

            batch = []
            for doc in cursor:
                new_doc = doc.copy()
                new_doc.pop('_id', None)
                batch.append(new_doc)

                if len(batch) >= BATCH_SIZE:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would insert batch of {len(batch)} documents")
                    else:
                        target_coll.insert_many(batch, ordered=False)
                    batch = []

            # Insert remaining documents
            if batch:
                if dry_run:
                    logger.info(f"[DRY RUN] Would insert final batch of {len(batch)} documents")
                else:
                    target_coll.insert_many(batch, ordered=False)

        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Completed! {'Would copy' if dry_run else 'Copied'} {total_docs} documents total")

        return {
            'status': 'success' if not dry_run else 'dry_run',
            'copied_count': total_docs,
            'date': scrape_date,
            'target': target_collection,
            'dry_run': dry_run
        }

    except Exception as e:
        logger.error(f"Error during copy operation: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'date': scrape_date,
            'dry_run': dry_run
        }

    finally:
        local_client.close()
        server_client.close()
