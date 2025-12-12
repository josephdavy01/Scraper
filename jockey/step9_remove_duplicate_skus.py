import os
import json
from datetime import datetime  # keep if used elsewhere, safe to remove if not needed


def remove_duplicates(data):
    seen = set()
    unique = []
    duplicates = []

    for item in data:
        if not isinstance(item, dict):
            continue  # safety check

        sku = item.get("sku")
        if not sku:
            unique.append(item)
            continue

        if sku not in seen:
            seen.add(sku)
            unique.append(item)
        else:
            duplicates.append(sku)

    return unique, duplicates


def process_country_data(country, fetch_date, file_type):
    folder = os.path.join(country, fetch_date, 'Final_json')

    # ✅ Ensure folder exists before reading/writing
    os.makedirs(folder, exist_ok=True)

    # Input file
    input_file = os.path.join(folder, f'{country}_{file_type}_data.json')

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

    # ✅ Safety: Ensure JSON root is a list
    if not isinstance(data, list):
        print(f"Invalid data format in {input_file} (Expected list)")
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

def run_duplicate_removal(countries, fetch_date):
    # ✅ Convert dict keys to list safely
    country_list = list(countries.keys()) if isinstance(countries, dict) else countries

    file_types = ['apparel']

    for country in country_list:
        print(f"Removing duplicates for {country}...")
        for f_type in file_types:
            process_country_data(country, fetch_date, f_type)

    print("\nDuplicate removal completed.")


# ---------------------------------- MAIN EXECUTION ----------------------------------

if __name__ == "__main__":
    from datetime import datetime
    
    TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
    # TODAY_DATE = "2025-12-11"
    COUNTRIES = {'India': 'India'}
    
    run_duplicate_removal(COUNTRIES, TODAY_DATE)
