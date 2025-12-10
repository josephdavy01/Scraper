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

def process_country_data(country, fetch_date):
    folder = os.path.join(country, fetch_date, 'Data')
    input_file = os.path.join(folder, 'apparel_products_data_' + country + '.json')
    output_file = os.path.join(folder, 'apparel_products_data_deduped_' + country + '.json')
    log_file = os.path.join(folder, f'apparel_duplicates_log_{fetch_date}.json')

    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    deduped, dup_skus = remove_duplicates(data)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)

    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(dup_skus, f, indent=2, ensure_ascii=False)

    print(f"{country}: Total = {len(data)}, Unique = {len(deduped)}, Duplicates = {len(dup_skus)}")

# ---------------------------------- ENTRY POINT ----------------------------------

def remove_duplicate_sku_apparel(countries, fetch_date, re_run=False):
    #Check if the data file exists  
    for country in countries.keys():
        folder = os.path.join(country, fetch_date, 'Data')
        input_file = os.path.join(folder, f"apparel_products_data_deduped_{country}.json")
        if not re_run and os.path.exists(input_file):
            print(f"Data file {input_file} already exists. Skipping processing for {country}.")
            continue
        process_country_data(country, fetch_date)

    print("\nDuplicate removal completed.")