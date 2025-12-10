import os
import json
import logging
import pandas as pd
from datetime import datetime
from collections import defaultdict

# IMPORT YOUR TICKET SYSTEM
try:
    from alert import raise_ticket
except ImportError:
    # Placeholder if alert.py isn't in the same folder during testing
    def raise_ticket(system, process, details, country):
        logging.warning(f"Simulating Ticket Raise for {country}: \n{details}")

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- DEFINING VALIDATION RULES ---
VALIDATION_SETS = {
    'gender': ['male', 'female', 'kids', 'unisex'],
    'availability': ['in_stock', 'out_of_stock', 'low_on_stock', 'back_soon', 'coming_soon'],
    'age_group': ['new_born', 'baby', 'junior', 'senior', 'teen', 'adult'],
    'age_range': [
        '0m', '1m', '2m', '3m', '4m', '5m', '6m', '7m', '8m', '9m', '10m', '11m', 
        '12m', '13m', '14m', '15m', '16m', '17m', '18m', '19m', '20m', '21m', '22m', 
        '23m', '24m', '2y', '3y', '4y', '5y', '6y', '7y', '8y', '9y', '10y', '11y', 
        '12y', '13y', '14y', '15y', '16y', '17y', '18y'
    ]
}

# --- MEMORY EFFICIENT HELPER (From Code 2) ---
def stream_json_array(file_obj):
    """
    Generator that yields JSON objects from a file containing a JSON array of objects.
    Reads chunk-by-chunk to save memory.
    """
    buffer = ""
    brace_count = 0
    in_string = False
    escape = False
    started = False
    
    while True:
        chunk = file_obj.read(4096) # Read 4KB at a time
        if not chunk:
            break
            
        for char in chunk:
            if not started:
                if char == '[':
                    started = True
                continue
            
            if char == ']' and brace_count == 0:
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
                        try:
                            obj_str = buffer.strip()
                            if obj_str.startswith(','):
                                obj_str = obj_str[1:].strip()
                            
                            yield json.loads(obj_str)
                            buffer = ""
                        except json.JSONDecodeError as e:
                            logging.warning(f"Failed to decode JSON object: {e}")
                            buffer = ""

# --- MAIN LOGIC ---

def check_data_format(today_str, country='India'):
    logging.info(f"Checking data format for {country} on {today_str}")
    
    # Define paths
    base_path = f'{country}/{today_str}/Data'
    files_to_check = []
    
    for cat in ['Apparel', 'Footwear']:
        file_path = f'{base_path}/{country}_data_{cat.lower()}.json'
        if os.path.exists(file_path):
            files_to_check.append((cat, file_path))
        else:
            logging.warning(f"{cat} file not found: {file_path}")

    if not files_to_check:
        logging.error("No data files found to check.")
        return

    for category, file_path in files_to_check:
        try:
            logging.info(f"Starting validation for {category}...")
            
            # --- AGGREGATOR DICTIONARY ---
            # Keys will be error messages, Values will be lists of Product IDs
            issues = defaultdict(list)
            item_count = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                
                # MEMORY EFFICIENT LOOP: Iterate over the generator instead of a list
                for item in stream_json_array(f):
                    item_count += 1
                    
                    pid = item.get('product_id', 'Unknown')
                    
                    # 1. Critical Missing Fields (Specific Logic)
                    if not item.get('price'):
                        issues['missing_price'].append(pid)
                    
                    if not item.get('sku'):
                        issues['missing_sku'].append(pid)
                    
                    # Check other mandatory fields for not None/Empty
                    for field in ['title', 'launch_price', 'gender', 'size_name', 'availability']:
                        val = item.get(field)
                        if val is None or (isinstance(val, str) and val.strip() == ""):
                            issues[f'missing_{field}'].append(pid)

                    # 2. Data Type Checks (Arrays)
                    for list_field in ['images', 'age_group', 'age_range']:
                        val = item.get(list_field)
                        if not isinstance(val, list):
                            issues[f'invalid_type_{list_field}'].append(pid)
                        # Specific check for empty images if strict validation is needed
                        elif list_field == 'images' and len(val) == 0:
                            issues['empty_images'].append(pid)

                    # 3. Numeric & Price Logic
                    try:
                        price = float(item.get('price', 0))
                        launch_price = float(item.get('launch_price', 0))
                        
                        if price < 0:
                            issues['negative_price'].append(pid)
                        
                        # Logic: Launch price must not be less than price
                        if launch_price < price:
                            issues['price_greater_than_launch_price'].append(pid)
                            
                    except (ValueError, TypeError):
                        issues['price_non_numeric'].append(pid)

                    # 4. Domain Checks (Enums)
                    if item.get('gender') not in VALIDATION_SETS['gender']:
                        issues['invalid_gender_value'].append(pid)

                    if item.get('availability') not in VALIDATION_SETS['availability']:
                        issues['invalid_availability_value'].append(pid)

                    # Check contents of age_group list
                    age_groups = item.get('age_group', [])
                    if isinstance(age_groups, list):
                        if any(ag not in VALIDATION_SETS['age_group'] for ag in age_groups):
                            issues['invalid_age_group_value'].append(pid)

                    # Check contents of age_range list
                    age_ranges = item.get('age_range', [])
                    if isinstance(age_ranges, list):
                        if any(ar not in VALIDATION_SETS['age_range'] for ar in age_ranges):
                             issues['invalid_age_range_value'].append(pid)

            # Check if file was empty based on counter
            if item_count == 0:
                logging.warning(f"{category} data is empty.")
                continue

            logging.info(f"Finished validating {item_count} items in {category}.")

            # --- SUMMARY AND TICKET LOGIC ---
            if not issues:
                logging.info(f"✅ {category} data passed validation.")
            else:
                # Build the summary string
                details_lines = []
                details_lines.append(f"Validation Issues found in {category}:")
                
                for issue_type, pids in issues.items():
                    # Deduplicate PIDs if needed
                    unique_pids = list(set(pids))
                    count = len(unique_pids)
                    details_lines.append(f"{issue_type}: {count} -> Product IDs: {unique_pids}")
                
                details = "\n".join(details_lines)
                
                # Print Summary Log
                logging.error(details)
                
                # Raise Ticket
                try:
                    raise_ticket("Master", "check_comparison_results_data", details, country)
                    logging.info("Ticket raised successfully.")
                except Exception as e:
                    logging.error(f"Failed to raise ticket: {e}")

        except Exception as e:
            logging.error(f"Error processing {category}: {e}")