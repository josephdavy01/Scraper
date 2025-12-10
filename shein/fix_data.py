import os
from pymongo import MongoClient, UpdateOne  # type: ignore
from datetime import datetime, timezone
import re

# Define constants
time_stamp = "20250422"  # Example timestamp
get_date = "2025-04-22"
WEBSITE_NAME = "SHEININDIA"

# MongoDB connection
client = MongoClient("mongodb://root:iK&dsCaTio976fghI*(bgdskk)~@3.1.227.250:28018/tg_analytics?authSource=admin")
# client = MongoClient("mongodb://localhost:27017/")
db = client["tg_analytics"]
collection = db["crawler_sink_shein_india"]

# Size mapping for SKU transformation
size_map = {
    "xs": "001",
    "s": "002",
    "m": "003",
    "l": "004",
    "xl": "005",
    "xxl": "006"
}

# SKU pattern matcher
sku_pattern = re.compile(r"^(shn\d+)%(\d+)_([a-zA-Z]+)(\d{3})([a-zA-Z]+)$")

try:
    # Convert get_date to UTC midnight
    dt = datetime.strptime(get_date, "%Y-%m-%d")
    dt_midnight_utc = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

    # Update date_of_scraping to UTC
    result_date = collection.update_many(
        {"date_of_scraping": {"$regex": f"^{get_date}"}},
        {"$set": {"date_of_scraping": dt_midnight_utc}}
    )
    print(f"Updated {result_date.modified_count} documents for date.")

    # Update gender: women → female
    result_women = collection.update_many(
        {"gender": "women"},
        {"$set": {"gender": "female"}}
    )
    print(f"Updated {result_women.modified_count} documents from 'women' to 'female'.")

    # Update gender: men → male
    result_men = collection.update_many(
        {"gender": "men"},
        {"$set": {"gender": "male"}}
    )
    print(f"Updated {result_men.modified_count} documents from 'men' to 'male'.")

    # Fetch documents for advanced updates
    docs = collection.find({"date_of_scraping": dt_midnight_utc})
    bulk_updates = []

    for doc in docs:
        update_fields = {}

        # Convert empty strings to None
        for field in ["size_ref_code", "demand", "description"]:
            if doc.get(field) == "":
                update_fields[field] = None

        # Convert origin to lowercase
        if "origin" in doc and isinstance(doc["origin"], str):
            update_fields["origin"] = doc["origin"].lower()

        # Convert price and launch_price from str to int
        for price_field in ["price", "launch_price"]:
            if price_field in doc and isinstance(doc[price_field], str) and doc[price_field].isdigit():
                update_fields[price_field] = int(doc[price_field])

        # Transform SKU format
        old_sku = doc.get("sku")
        if old_sku:
            match = sku_pattern.match(old_sku)
            if match:
                part1, part2, color, color_code, size = match.groups()
                size = size.lower()
                size_code = size_map.get(size)
                if size_code:
                    color_code = color_code.zfill(3)  # Ensure 3-digit format
                    new_sku = f"{part1}%p{part2}c{color_code}s{size_code}"
                    update_fields["sku"] = new_sku

        # Update image_style in images array
        images = doc.get("images")
        if isinstance(images, list):
            updated_images = []
            for idx, image in enumerate(images):
                if isinstance(image, dict):
                    image["image_style"] = f"s{idx}"
                    updated_images.append(image)
            update_fields["images"] = updated_images

        if update_fields:
            bulk_updates.append(
                UpdateOne({"_id": doc["_id"]}, {"$set": update_fields})
            )

    # Apply bulk updates
    if bulk_updates:
        result_bulk = collection.bulk_write(bulk_updates)
        print(f"Bulk update: Modified {result_bulk.modified_count} documents.")
    else:
        print("No documents needed bulk update.")

except Exception as e:
    print(f"Error during conversion: {e}")
