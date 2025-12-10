import json
import os
from datetime import datetime

today = '2025-10-30'
BASE_DIR = os.path.join("UK", "data", today)
ITEM_DIR = os.path.join(BASE_DIR, "item_urls")
os.makedirs(ITEM_DIR, exist_ok=True)

INPUT_FILE = os.path.join(ITEM_DIR, "All_Product_URLs_by_Category.json")
OUTPUT_UNIQUE = os.path.join(ITEM_DIR, "All_Product_URLs_Unique.json")

unique_urls = set()

print("⏳ Collecting unique URLs...")

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)
    for main_cat, subcats in data.items():
        if isinstance(subcats, dict):
            for subcat_name, urls in subcats.items():
                if isinstance(urls, list):
                    unique_urls.update([u.strip() for u in urls if isinstance(u, str) and u.strip()])

print(f"✅ Found {len(unique_urls)} unique URLs. Saving...")

with open(OUTPUT_UNIQUE, "w", encoding="utf-8") as f:
    json.dump(sorted(unique_urls), f, indent=2, ensure_ascii=False)

print(f"✅ Done! File saved to: {OUTPUT_UNIQUE}")
