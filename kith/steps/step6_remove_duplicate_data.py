# remove_duplicates.py
# Removes duplicate SKU entries from a JSON list and logs them separately

import os
import json
from datetime import datetime

# ---------------------------------- UTILITY ----------------------------------

def remove_duplicates(data):
    seen = set()
    unique = []
    duplicates = []
    for item in data:
        sku = item.get("sku")
        if sku not in seen:
            seen.add(sku)
            unique.append(item)
        else:
            duplicates.append(sku)
    return unique, duplicates

# ---------------------------------- MAIN LOGIC ----------------------------------

def process_country_data(country, fetch_date, file_type):
    folder = os.path.join(country, fetch_date, 'Data')
    # Input file matches the output from step 7/8: {country}_data_{file_type}.json
    input_file = os.path.join(folder, f'{country}_data_{file_type}.json')
    # Log file for duplicates
    log_file = os.path.join(folder, f'duplicate_skus_{file_type}.json')

    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {input_file}: {e}")
        return

    deduped, dup_skus = remove_duplicates(data)

    # Save unique data back to the SAME file
    try:
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(deduped, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error writing to {input_file}: {e}")

    # Save duplicates to log file
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(dup_skus, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error writing to {log_file}: {e}")

    print(f"{country} [{file_type}]: Total = {len(data)}, Unique = {len(deduped)}, Duplicates = {len(dup_skus)}")

# ---------------------------------- ENTRY POINT ----------------------------------

def remove_duplicates_from_json(countries, fetch_date):
    # If countries is a dict (like in master.py), we iterate keys. If list, iterate items.
    country_list = countries.keys() if isinstance(countries, dict) else countries
    
    file_types = ['footwear', 'apparel']

    for country in country_list:
        print(f"Removing duplicates for {country}...")
        for f_type in file_types:
            process_country_data(country, fetch_date, f_type)

    print("\nDuplicate removal completed.")