import json
from pathlib import Path
from datetime import datetime, timezone
from pymongo import MongoClient, InsertOne

CHUNK_SIZE = 1000

def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def convert_dates(obj):
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                convert_dates(item)
    elif isinstance(obj, dict):
        if "date_of_scraping" in obj:
            try:
                dt = datetime.fromisoformat(obj["date_of_scraping"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                obj["date_of_scraping"] = dt
            except (ValueError, TypeError):
                pass
    return obj

def upload_to_mongodb_in_chunks(data, country, today_date, db_config):
    if not data:
        print(f"[{country}] No apparel data to upload.")
        return
        
    force_upload = db_config.get('FORCE_UPLOAD', False)
    client = MongoClient(db_config['LOCAL_URI'])
    db = client["tg_analytics"] # Specific DB for apparel
    collection = db[f"crawler_sink_puma_{country.lower()}"]
    
    upload_date = datetime.fromisoformat(today_date).replace(tzinfo=timezone.utc)
    date_filter = {"date_of_scraping": upload_date}

    # --- FIX: Check for existing data and act based on FORCE_UPLOAD ---
    existing_count = collection.count_documents(date_filter)
    if existing_count > 0:
        if force_upload:
            print(f"[{country}] FORCE_UPLOAD is True. Deleting {existing_count} existing apparel documents for {today_date}.")
            collection.delete_many(date_filter)
        else:
            print(f"[{country}] Apparel data for {today_date} is already uploaded ({existing_count} docs). Skipping.")
            return

    total_inserted = 0
    for batch in chunked(data, CHUNK_SIZE):
        operations = [InsertOne(item) for item in batch]
        try:
            result = collection.bulk_write(operations)
            total_inserted += result.inserted_count
        except Exception as e:
            print(f"[{country}] Error inserting apparel batch: {e}")

    print(f"[{country}] Inserted {total_inserted} new apparel documents into collection 'crawler_sink_puma_{country.lower()}'.")

def load_to_db_apparel(TODAY_DATE, COUNTRIES, db_config):
    for country in COUNTRIES:
        output_dir = Path(country) / TODAY_DATE / "Data"
        combined_file = output_dir / f"apparel_products_data_deduped_{country}.json"

        if not combined_file.exists():
            print(f"[{country}] Apparel file not found: {combined_file}")
            continue

        try:
            with open(combined_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                data = convert_dates(raw_data)
        except json.JSONDecodeError:
            print(f"[{country}] Failed to load apparel JSON: {combined_file}")
            continue

        upload_to_mongodb_in_chunks(data, country, TODAY_DATE, db_config)