import os
import ast
import json
from datetime import date, datetime

def create_new_entry(pdict, plist):
    """Create a new group entry in the PID dictionary."""
    pid = plist[0]
    pdict[pid] = plist
    print(f'New entry {pid}: {pdict[pid]}')
    return pid

def update_entry(pdict, plist):
    """Update an existing group with new pids or create a new one."""
    for i, j in pdict.items():
        if any(pid in j for pid in plist):
            updated_list = list(set(j) | set(plist))
            updated_list.sort()
            pdict[i] = updated_list
            print(f'Group {i} updated: {pdict[i]}')
            return
    create_new_entry(pdict, plist)

def get_pid(pdict, plist):
    """Ensure pids are grouped correctly by checking existing groups."""
    found = False
    for pid in plist:
        for group in pdict.values():
            if pid in group:
                found = True
                break
        if found:
            break
    if not found:
        update_entry(pdict, plist)

def process_pids(pdict, cdict, main_folder):
    """Process product JSON files to extract and update PID and CID mappings."""
    # Categories to skip - only process apparel and footwear
    skip_categories = ['bags', 'belts', 'perfumes', 'sunglasses', 'accessories']
    
    # Walk through the main folder recursively
    for root, _, files in os.walk(main_folder):
        for file in files:
            if not file.endswith('.json'):
                continue
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as json_file:
                    data = json.load(json_file)

                product = data['product']
                
                # Check product type and skip unwanted categories
                product_type = product.get('shopify_product_type', '').strip().lower()
                if any(skip_cat in product_type for skip_cat in skip_categories):
                    continue  # Skip this product entirely
                
                # Handle color ID assignment (only for apparel/footwear)
                try:
                    color_raw = product.get('color')
                    if color_raw and color_raw != 'None':  # Check if color exists and is not None
                        color = ast.literal_eval(color_raw)[0]
                        if color:
                            color = color.lower().strip()
                        if color not in cdict:
                            cid = f"{len(cdict) + 1:03}"
                            cdict[color] = cid
                except Exception as e:
                    # Only print error for products we're actually processing
                    if product_type == 'shoes' or product_type not in skip_categories:
                        print(f'Error {e} while getting color from {file_path}')

                # Handle PID grouping
                try:
                    pids = product.get('color_variants_ids', [])
                    if not isinstance(pids, list):
                        pids = []
                    pids.append(product.get('shopify_product_id'))
                    pids = list(set(pids))
                    pids.sort()
                    get_pid(pdict, pids)
                except Exception as e:
                    print(f'Error {e} while getting pids from {file_path}')
            except Exception as e:
                print(f'Failed to read {file_path}: {e}')

def update_pids_cids(today_str):
    country = 'India'
    main_folder = os.path.join(country, today_str, 'Json_data')

    pid_path = 'snitch_pid_remapping.json'
    cid_path = 'snitch_cid_remapping.json'

    # Load existing remappings or initialize new ones
    if os.path.exists(pid_path):
        with open(pid_path, 'r') as json_file:
            pdict = json.load(json_file)
    else:
        pdict = {}

    if os.path.exists(cid_path):
        with open(cid_path, 'r') as json_file:
            cdict = json.load(json_file)
    else:
        cdict = {}

    # Process files and update mappings
    process_pids(pdict, cdict, main_folder)

    # Save updated mappings
    with open(pid_path, 'w') as f:
        json.dump(pdict, f, indent=2)

    with open(cid_path, 'w') as f:
        json.dump(cdict, f, indent=2)

    print(f' PIDs and CIDs for {country} on {today_str} updated.')

if __name__ == "__main__":
    today = date.today().strftime('%Y-%m-%d')
    update_pids_cids(today)

