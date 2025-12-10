import os
import json
import re
from datetime import date

def normalize_sku(sku: str) -> str:
    sku = sku.strip().lower()
    sku = re.sub(r'\d+r?$', '', sku)
    m = re.match(r'([a-z0-9]+up)', sku)
    if m:
        return m.group(1)
    m = re.match(r'([a-z0-9]+[mwupr])', sku)
    if m:
        return m.group(1)
    return sku

def create_new_entry(pdict, pid, skus, new_pids):
    pdict[pid] = list(set(skus))
    new_pids.add(pid)
    return pid

def update_entry(pdict, pid, skus, new_pids):
    if pid in pdict:
        before = set(pdict[pid])
        after = before | set(skus)
        pdict[pid] = list(after)
        if after != before:
            print(f'Updated PIDs {pid} with new SKUs: {list(after - before)}')
    else:
        create_new_entry(pdict, pid, skus, new_pids)

def process_pids(pdict, main_folder, new_pids):
    """Process all JSON files under a geography/date folder."""
    if not os.path.exists(main_folder):
        print(f"Folder not found: {main_folder}")
        return

    # Only consider directories (genders)
    genders = [d for d in os.listdir(main_folder) if os.path.isdir(os.path.join(main_folder, d))]
    for gender in genders:
        gender_folder = os.path.join(main_folder, gender)

        # Only consider directories (categories)
        categories = [c for c in os.listdir(gender_folder) if os.path.isdir(os.path.join(gender_folder, c))]
        for category in categories:
            category_folder = os.path.join(gender_folder, category)
            files = [f for f in os.listdir(category_folder) if f.endswith('.json')]
            for file in files:
                file_path = os.path.join(category_folder, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    pid = None
                    skus_to_add = []
                    url = None
                    valid_skus = []

                    # --- NEW LOGIC TO HANDLE COMPLEX JSON STRUCTURE ---
                    # Check if the data is in the new, nested format
                    if 'data' in data and 'products' in data['data']:
                        try:
                            # Try to get the URL from the first product node
                            if data['data']['products']['edges']:
                                url = data['data']['products']['edges'][0]['node'].get('onlineStoreUrl')

                            # Extract all SKUs from all product variants
                            for product_edge in data['data']['products']['edges']:
                                variants = product_edge.get('node', {}).get('variants', {}).get('edges', [])
                                for variant_edge in variants:
                                    sku = variant_edge.get('node', {}).get('sku')
                                    if sku and sku.strip():
                                        valid_skus.append(sku)
                        except (KeyError, IndexError, TypeError):
                            print(f"Warning: Could not parse nested JSON structure in {file_path}")
                    else:
                        # Fallback to the old, simple structure
                        url = data.get('onlineStoreUrl')
                        valid_skus = [s for s in data.get('skus', []) if s and s.strip()]


                    # --- EXISTING PID DETERMINATION LOGIC (Now with correct data) ---
                    if url:
                        match = re.search(r'/products/([a-zA-Z0-9-]+)', url)
                        if match:
                            pid = normalize_sku(match.group(1))

                    if not pid and valid_skus:
                        all_base_pids = sorted(list(set(normalize_sku(s) for s in valid_skus)))
                        if all_base_pids:
                            pid = all_base_pids[0]
                            skus_to_add = all_base_pids
                    
                    if pid and not skus_to_add:
                        skus_to_add = [pid] + [normalize_sku(s) for s in valid_skus]


                    if pid:
                        update_entry(pdict, pid, skus_to_add, new_pids)
                    else:
                        print(f"Warning: Could not determine PID for {file_path}")

                except Exception as e:
                    print(f"Error in {file_path}: {e}")
                    continue


def remap_pids(countries, today_date):
    """
    Processes product data for a specific date to create a mapping of PIDs to SKUs.
    This function reads product JSON files from the specified date's folder for each country,
    updates a central PID mapping file, and logs the number of new PIDs found.
    """
    pid_path = 'alo_pid_remapping.json'

    # Load existing PID mapping
    if os.path.exists(pid_path):
        with open(pid_path, 'r', encoding='utf-8') as f:
            pdict = json.load(f)
    else:
        pdict = {}

    new_pids = set()
    print(f"\n--- Starting PID Remapping for {today_date} ---")

    # The 'countries' argument should be a dictionary like the one in master.py
    for country in countries.keys():
        print(f"Processing PIDs for {country}...")
        main_folder = os.path.join(country, today_date, 'Json_data')
        if os.path.exists(main_folder):
            process_pids(pdict, main_folder, new_pids)
        else:
            print(f"Warning: Data folder not found for {country} on {today_date}: {main_folder}")

    # Save updated PID mapping
    with open(pid_path, 'w', encoding='utf-8') as f:
        json.dump(pdict, f, indent=4)

    print(f"--- PID Remapping complete. {len(new_pids)} new PIDs added. ---")
    if new_pids:
        print(f"New PIDs: {list(new_pids)}")
