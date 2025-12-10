import logging
import os
import json
from datetime import date, datetime
from pathlib import Path

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------------- UTILITY ----------------------------------

def stream_json_array(file_obj):
    """
    Generator that yields JSON objects from a file containing a JSON array of objects.
    This is a simplified parser that assumes standard formatting (e.g. [ { ... }, { ... } ]).
    """
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

# ---------------------------------- VALIDATION LOGIC ----------------------------------

def validate_item(item, errors):
    """
    Validates a single item and updates the errors dictionary.
    """
    # Required fields check
    required_fields = ['product_id', 'price', 'launch_price', 'availability', 'color_name', 'sku', 'gender', 'title', 'age_group', 'age_range']
    for field in required_fields:
        if item.get(field) is None:
            errors[f"'{field}' contains None"] = True

    # Type checks and value checks
    if item.get('gender') not in ['male', 'female', 'unisex'] and item.get('gender') is not None:
        errors["'gender' contains invalid values"] = True
        
    if item.get('availability') not in ['in_stock', 'out_of_stock', 'low_on_stock', 'back_soon', 'coming_soon'] and item.get('availability') is not None:
        errors["'availability' contains invalid values"] = True
        
    price = item.get('price')
    if price is not None and not isinstance(price, (int, float)):
        errors["'price' contains non-numeric values"] = True
        
    launch_price = item.get('launch_price')
    if launch_price is not None and not isinstance(launch_price, (int, float)):
        errors["'launch_price' contains non-numeric values"] = True
        
    for field in ['sku', 'title', 'color_name']:
        val = item.get(field)
        if val is not None and not isinstance(val, str):
            errors[f"'{field}' contains non-string values"] = True

    # Age group check
    valid_age_groups = ['new_born', 'baby', 'junior', 'senior', 'teen', 'adult']
    age_groups = item.get('age_group')
    if age_groups:
        for ag in age_groups:
            if ag not in valid_age_groups:
                errors[f"'age_group' contains invalid values: {ag}"] = True

    # Age range check
    valid_age_ranges = ['0m', '1m', '2m', '3m', '4m', '5m', '6m', '7m', '8m', '9m', '10m', '11m', '12m', '13m', '14m', '15m', '16m', '17m', '18m', '19m', '20m', '21m', '22m', '23m', '24m', '2y', '3y', '4y', '5y', '6y', '7y', '8y', '9y', '10y', '11y', '12y', '13y', '14y', '15y', '16y', '17y', '18y']
    age_ranges = item.get('age_range')
    if age_ranges:
        for ar in age_ranges:
            if ar not in valid_age_ranges:
                errors[f"'age_range' contains invalid values: {ar}"] = True

def check_file(file_path, geography, date_str):
    if not file_path.exists():
        logging.error(f"File not found: {file_path}")
        return

    logging.info(f"Checking format for {file_path}...")
    errors = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Use streaming parser
            for item in stream_json_array(f):
                validate_item(item, errors)
                
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return

    if not errors:
        logging.info(f"Data format check passed for {file_path.name}. All fields are correctly formatted.")
    else:
        logging.error(f"Data format check failed for {file_path.name}.")
        for error in errors:
            logging.error(f"Data format error in {geography} for date {date_str}: {error}")

def check_data_format(geography, date_str):
    folder = Path(geography) / date_str / 'Data'
    
    # Check Apparel
    apparel_file = folder / f'{geography}_data_apparel.json'
    check_file(apparel_file, geography, date_str)
    
    # Check Footwear
    footwear_file = folder / f'{geography}_data_footwear.json'
    check_file(footwear_file, geography, date_str)
