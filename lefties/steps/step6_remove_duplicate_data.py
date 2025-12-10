# remove_duplicates.py
# Removes duplicate SKU entries from a JSON list and logs them separately
# Optimized for large files using streaming (custom generator)

import os
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------------- UTILITY ----------------------------------

def stream_json_array(file_obj):
    """
    Generator that yields JSON objects from a file containing a JSON array of objects.
    This is a simple parser that assumes standard formatting (e.g. [ { ... }, { ... } ]).
    It reads character by character/chunk to find object boundaries.
    """
    # This is a simplified streaming parser for an array of objects.
    # It relies on counting braces to identify objects.
    # It is not a full JSON parser but works for standard scraped data.
    
    buffer = ""
    brace_count = 0
    in_string = False
    escape = False
    started = False
    
    while True:
        chunk = file_obj.read(4096)
        if not chunk:
            break
            
        for char in chunk:
            if not started:
                if char == '[':
                    started = True
                continue
            
            if char == ']' and brace_count == 0:
                # End of array
                return

            buffer += char
            
            if char == '"' and not escape:
                in_string = not in_string
            
            if char == '\\' and not escape:
                escape = True
            else:
                escape = False
                
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # End of an object
                        try:
                            # Remove trailing comma if present in buffer before this object (not likely inside the object string)
                            # Actually, the buffer contains the object text.
                            # We might have captured a comma before the object if we are not careful.
                            # But here we start buffer at '{' ideally.
                            
                            # Let's refine: buffer should accumulate ONLY the object.
                            # But we are just accumulating everything.
                            # We need to trim leading comma/whitespace.
                            
                            obj_str = buffer.strip()
                            if obj_str.startswith(','):
                                obj_str = obj_str[1:].strip()
                            
                            yield json.loads(obj_str)
                            buffer = ""
                        except json.JSONDecodeError as e:
                            logging.warning(f"Failed to decode JSON object: {e}")
                            buffer = ""

# ---------------------------------- MAIN LOGIC ----------------------------------

def process_country_data(country, fetch_date, file_type):
    folder = Path(country) / fetch_date / 'Data'
    input_file = folder / f'{country}_data_{file_type}.json'
    log_file = folder / f'duplicate_skus_{file_type}.json'
    temp_file = folder / f'{country}_data_{file_type}_temp.json'

    if not input_file.exists():
        logging.warning(f"File not found: {input_file}")
        return

    logging.info(f"Processing {input_file} for duplicates...")

    seen_skus = set()
    duplicate_skus = []
    unique_count = 0
    total_count = 0

    try:
        with open(input_file, 'r', encoding='utf-8') as f_in, open(temp_file, 'w', encoding='utf-8') as f_out:
            f_out.write('[\n')
            first_item = True
            
            # Use custom streaming parser
            # If the file is small enough, we could use json.load, but we assume it's huge.
            # If the custom parser is too risky, we can try a hybrid approach:
            # If file size < 500MB, use json.load. Else use parser.
            # But let's try to be robust.
            
            # Actually, standard json.load is safer if we have RAM. 
            # 17GB is too big.
            # Let's use a simpler approach: ijson is best. 
            # Since ijson failed, let's try to use the 'json' library's raw_decode in a loop?
            # No, raw_decode needs the string.
            
            # Let's try to use the simple parser defined above.
            for item in stream_json_array(f_in):
                total_count += 1
                sku = item.get("sku")
                
                if sku and sku not in seen_skus:
                    seen_skus.add(sku)
                    
                    if not first_item:
                        f_out.write(',\n')
                    
                    json.dump(item, f_out, default=str, indent=4)
                    first_item = False
                    unique_count += 1
                else:
                    if sku:
                        duplicate_skus.append(sku)
            
            f_out.write('\n]')

        # Replace original file with temp file
        if temp_file.exists():
            if temp_file.stat().st_size > 2:
                input_file.unlink()
                temp_file.rename(input_file)
                logging.info(f"Replaced original file with deduped data.")
            else:
                logging.warning("Temp file is empty or too small, not replacing original.")
                temp_file.unlink()

        # Save duplicates to log file
        if duplicate_skus:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(duplicate_skus, f, indent=4, ensure_ascii=False)
            logging.info(f"Saved {len(duplicate_skus)} duplicate SKUs to {log_file}")
        else:
            logging.info("No duplicates found.")

        logging.info(f"{country} [{file_type}]: Total = {total_count}, Unique = {unique_count}, Duplicates = {len(duplicate_skus)}")

    except Exception as e:
        logging.error(f"Error processing {input_file}: {e}")
        if temp_file.exists():
            temp_file.unlink()

# ---------------------------------- ENTRY POINT ----------------------------------

def remove_duplicates_from_json(countries, fetch_date):
    country_list = countries.keys() if isinstance(countries, dict) else countries
    file_types = ['footwear', 'apparel']

    for country in country_list:
        logging.info(f"Removing duplicates for {country}...")
        for f_type in file_types:
            process_country_data(country, fetch_date, f_type)

    logging.info("Duplicate removal completed.")