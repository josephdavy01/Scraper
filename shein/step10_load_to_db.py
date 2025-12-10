import os
from pymongo import MongoClient # type: ignore
from datetime import datetime, timezone
import time
import json

def start_step10():
    time_stamp = datetime.now().strftime("%Y%m%d")
    # time_stamp = '20250929'
    # "  # example timestamp, adjust as needed

    get_date = datetime.now().strftime("%Y-%m-%d")
    WEBSITE_NAME = "SHEININDIA"
    # Connect to MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    db = client["tg_analytics"]
    collection = db["crawler_sink_shein_india"]

    base_path = f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}"
    JSON_FILE_PATH  = os.path.join(base_path, "product_data.json")
    BATCH_SIZE = 5000  # Tune this based on system RAM and MongoDB capacity

    # Load JSON file
    with open(JSON_FILE_PATH, "r") as f:
        data = json.load(f)

    # Ensure it's a list
    if not isinstance(data, list):
        data = [data]

    # Chunk and insert
    def chunks(lst, size):
        for i in range(0, len(lst), size):
            yield lst[i:i + size]

    start_time = time.time()

    inserted_count = 0
    for batch in chunks(data, BATCH_SIZE):
        result = collection.insert_many(batch)
        inserted_count += len(result.inserted_ids)

    elapsed = time.time() - start_time

    print(f"Inserted {inserted_count} documents in {elapsed:.2f} seconds.")


    # Convert the specified date to UTC midnight datetime
    try:
        # Parse the target date string into a datetime object with the specified date
        dt = datetime.strptime(get_date, "%Y-%m-%d")
        dt_midnight_utc = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

        # Update documents where `date_of_scrapping` contains the specified date
        result = collection.update_many(
            {"date_of_scraping": {"$regex": f"^{get_date}"}} , 
            {"$set": {"date_of_scraping": dt_midnight_utc}} 
        )

        print(f"Updated {result.modified_count} documents.")
    except Exception as e:
        print(f"Error during conversion: {e}")

    return True
if __name__ == "__main__":
    start_step10()