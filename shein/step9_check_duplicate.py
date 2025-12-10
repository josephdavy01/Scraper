import json
from datetime import datetime,timezone
import os

def start_step9():
    # Dynamic file path
    WEBSITE_NAME = "SHEININDIA"
    time_stamp = datetime.now().strftime("%Y%m%d") 
    # time_stamp = '20250929'
     # example timestamp, adjust as needed
    base_path = f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}"
    input_file = os.path.join(base_path, "product_data.json")
    duplicates_file = os.path.join(base_path, "removed_duplicates.json")

    # Load JSON data
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Step 1: Remove duplicates and collect removed entries
    seen_skus = set()
    unique_data = []
    removed_duplicates = []

    for item in data:
        sku = item.get("sku")
        if sku and sku not in seen_skus:
            seen_skus.add(sku)
            unique_data.append(item)
        else:
            removed_duplicates.append(item)

    # Step 2: Save cleaned data
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(unique_data, f, indent=2)

    # Step 3: Save removed duplicates
    with open(duplicates_file, "w", encoding="utf-8") as f:
        json.dump(removed_duplicates, f, indent=2)

    print(f"Cleaned data saved to: {input_file}")
    print(f"Removed {len(removed_duplicates)} duplicates, saved to: {duplicates_file}")
    return True
if __name__ == "__main__":
    start_step9()