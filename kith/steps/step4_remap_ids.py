import os
import json
import logging

def extract_color_from_title(title):
    """Splits a title into a clean name and a color part."""
    parts = title.split(" - ")
    if len(parts) >= 2:
        clean_title = parts[0].strip().lower()
        color_part = parts[-1].strip().lower()
        return clean_title, color_part
    else:
        clean_title = title.strip().lower()
        return clean_title, ""

def find_all_json_files(root_dir):
    """Finds all .json files in a directory and its subdirectories."""
    json_files = []
    if not os.path.exists(root_dir) or not os.path.isdir(root_dir):
        logging.warning(f"JSON data directory not found: {root_dir}")
        return json_files
        
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.json') and 'scrape_log' not in file:
                json_files.append(os.path.join(root, file))
    return json_files

def remap_ids(countries, date_str):
    """
    Processes scraped JSON data to create and update product (PID) and color (CID) mappings.
    """
    logging.info("Starting Step 5: Remapping PIDs and CIDs.")
    
    pid_path = 'kith_pid_remapping.json'
    cid_path = 'kith_cid_remapping.json'

    try:
        with open(pid_path, 'r', encoding='utf-8') as f:
            pdict = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pdict = {}

    try:
        with open(cid_path, 'r', encoding='utf-8') as f:
            cdict = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cdict = {}

    for country in countries:
        logging.info(f"Processing {country} for remapping...")
        json_data_root = os.path.join(country, date_str, 'Json_data')
        
        json_files = find_all_json_files(json_data_root)
        logging.info(f"Found {len(json_files)} JSON files to process for {country}.")

        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as json_file:
                    data = json.load(json_file)
                    product_json = data.get("product_json", {})
                    original_title = product_json.get("title", "")
                    
                    if not original_title:
                        logging.warning(f"No title found in {file_path}")
                        continue
                    
                    clean_title, color_name = extract_color_from_title(original_title)
                    
                    if clean_title and clean_title not in pdict:
                        valid_ids = [int(v) for v in pdict.values() if isinstance(v, str) and v.isdigit()]
                        new_id_num = max(valid_ids) + 1 if valid_ids else 1
                        pid = f"{new_id_num:07}"
                        pdict[clean_title] = pid
                    
                    if color_name and color_name not in cdict:
                        cno = len(cdict) + 1
                        cid = f"{cno:04}"
                        cdict[color_name] = cid

            except Exception as e:
                logging.error(f"Error while processing {file_path}: {e}")

    with open(pid_path, 'w', encoding='utf-8') as f:
        json.dump(pdict, f, indent=2)

    with open(cid_path, 'w', encoding='utf-8') as f:
        json.dump(cdict, f, indent=4)

    logging.info(f"Processing complete. Total PIDs: {len(pdict)}, Total CIDs: {len(cdict)}")
    return True
