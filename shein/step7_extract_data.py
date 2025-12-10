import json
import logging
import os, sys
import re
import threading
import time
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from glob import glob

import concurrent.futures

#multi threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Specify the path to the manually downloaded ChromeDriver
chrome_driver_path = 'chromedriver.exe'

#Common variables
error_log = []
WEBSITE_NAME = "SHEININDIA"
WEBSITE_URL = "https://www.sheinindia.in/"
time_stamp = datetime.now().strftime("%Y%m%d")
# time_stamp = '20250929'

os.makedirs(f"{WEBSITE_NAME}/CATEGORY/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/COLsiOR_CODE", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/RAW_DATA", exist_ok=True)

# def create_driver():
#     chrome_options = Options()
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_argument("--headless")  # Run in headless mode
#     service = ChromeService(executable_path=chrome_driver_path)
#     return webdriver.Chrome(service=service, options=chrome_options)
def create_driver():
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Suppress logs
    service = Service(log_path='NUL')  # 'NUL' for Windows, '/dev/null' for Linux/macOS

    driver = webdriver.Chrome(service=service, options=options)
    return driver


def log_error(message, website=None, category=None, subcategory=None, sub_sub=None, url=None):
    """Log errors with detailed information."""
    error_log.append({
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "subcategory": subcategory,
        "sub_subcategory": sub_sub,
        "url": url,
        "message": message,
        "website": website
    })

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SIZE_MAPPING_FILE = f"{WEBSITE_NAME}/COLOR_CODE/size.json"
ERROR_LOG_FILE = f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/processing_errors.json"

def initialize_error_log():
    """Initialize error log file with empty list if it doesn't exist"""
    os.makedirs(os.path.dirname(ERROR_LOG_FILE), exist_ok=True)
    if not os.path.exists(ERROR_LOG_FILE):
        with open(ERROR_LOG_FILE, 'w') as f:
            json.dump([], f)

def log_error_to_file(error_data):
    """Append error information to the error log JSON file"""
    try:
        initialize_error_log()
        with open(ERROR_LOG_FILE, 'r+') as f:
            errors = json.load(f)
            errors.append(error_data)
            f.seek(0)
            json.dump(errors, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write to error log: {str(e)}")

# Load color code mapping
if os.path.exists(f"{WEBSITE_NAME}/COLOR_CODE/color_code.json"):
    with open(f"{WEBSITE_NAME}/COLOR_CODE/color_code.json", "r", encoding="utf-8") as file:
        color_code = json.load(file)
else:
    color_code = {
        "color_to_code": {},
        "code_to_color": {}
    }


def safe_load_json(filepath):
    """Load JSON file with error handling and logging"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        error_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filepath": filepath,
            "error_type": "Invalid JSON",
            "message": str(e),
            "action": "Skipped file"
        }
        log_error_to_file(error_data)
        logger.error(f"Error loading {filepath}: {str(e)}")
        return None
    
def validate_product_structure(json_data, filepath):
    """Validate the product JSON structure and log errors"""
    if not json_data:
        error_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filepath": filepath,
            "error_type": "Empty File",
            "message": "File contains no data",
            "action": "Skipped file"
        }
        log_error_to_file(error_data)
        return False
    
    if not isinstance(json_data, list) or not json_data[0].get('productDetails'):
        error_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filepath": filepath,
            "error_type": "Invalid Structure",
            "message": "Missing required productDetails structure",
            "action": "Skipped file"
        }
        log_error_to_file(error_data)
        return False
    
    return True

def load_color_codes():
    """Load color code mapping with error handling"""
    color_file = f"{WEBSITE_NAME}/COLOR_CODE/color_code.json"
    try:
        if os.path.exists(color_file):
            with open(color_file, "r", encoding="utf-8") as file:
                return json.load(file)
    except Exception as e:
        logger.error(f"Error loading color codes: {str(e)}")
    
    return {"color_to_code": {}, "code_to_color": {}}
    
def load_size_mapping():
    """Load existing size mapping from JSON file or initialize an empty one."""
    if os.path.exists(SIZE_MAPPING_FILE):
        with open(SIZE_MAPPING_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

def save_size_mapping(size_mapping):
    """Save updated size mapping to JSON file without overwriting existing data."""
    with open(SIZE_MAPPING_FILE, "w", encoding="utf-8") as file:
        json.dump(size_mapping, file, indent=4)

def get_size_code(size):
    """Fetch or assign a size code dynamically, ensuring three-digit format."""
    size_mapping = load_size_mapping()

    if size not in size_mapping:
        # Assign new code sequentially, preserving previous codes
        new_code = f"{max(map(int, size_mapping.values()), default=0) + 1:03d}"
        size_mapping[size] = new_code
        save_size_mapping(size_mapping)  # Save the updated mapping
    
    return size_mapping[size]

# Ensure the default sizes are stored if the file is empty
size_mapping = load_size_mapping()
if not size_mapping:
    default_sizes = {
        "xs": "001", "s": "002", "m": "003", "l": "004", "xl": "005",
        "xxl": "006", "xxxl": "007"
    }
    size_mapping.update(default_sizes)
    save_size_mapping(size_mapping)

def extract_composition(product_details):
    """Extract fabric composition from featureData (only from 'fabricDetail', returns null if not found)"""
    feature_data = product_details.get("featureData", [])
    for feature in feature_data:
        if feature.get("catalogAttributeName") == "fabricDetail":
            feature_values = feature.get("featureValues", [])
            if feature_values:
                return feature_values[0].get("value")
    return None  # Explicitly return None if fabricDetail is not found

def extract_images(product_details):
    """Extract image URLs where format is 'superZoomPdp' and imageType is 'GALLERY' with sequential numbering"""
    image_data_list = []
    images = product_details.get("images", [])
    style_counter = 0  # Initialize counter for sequential numbering
    
    for image in images:
        if (image.get("format") == "superZoomPdp" and 
            image.get("imageType") == "GALLERY"):
            image_data_list.append({
                "url": image["url"],
                "image_style": f"s{style_counter}"  # s0, s1, s2, etc.
            })
            style_counter += 1  # Increment only for matching images
    
    return image_data_list

def extract_sizes_and_stock(data, variant_key='variantOptions'):
    extracted_data = []
    
    product_details = data[0].get('productDetails', {})
    variants = product_details.get(variant_key, [])
    
    for variant in variants:
        # Prefer scDisplaySize, fallback to qualifier-based extraction
        size = variant.get('scDisplaySize')
        if not size:
            qualifiers = variant.get('variantOptionQualifiers', [])
            for q in qualifiers:
                if q.get('qualifier') == 'size':
                    size = q.get('value')
                    break  # Stop once size is found

        stock_status = variant.get('stock', {}).get('stockLevelStatus')
        price = variant.get('priceData', {}).get('value')

        if size and stock_status:
            extracted_data.append({
                'size': size,
                'stock_status': stock_status,
                'price': price
            })

    return extracted_data

def process_product_file(filepath):
    """Process a single product file with comprehensive error handling"""
    json_data = safe_load_json(filepath)
    if not json_data or not validate_product_structure(json_data, filepath):
        return None
    
    product_details = json_data[0]['productDetails']
    
    # Validate required fields
    required_fields = ['baseProduct', 'name', 'code', 'url']
    if not all(field in product_details for field in required_fields):
        error_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filepath": filepath,
            "error_type": "Missing Fields",
            "message": f"Missing one or more required fields: {required_fields}",
            "action": "Skipped file"
        }
        log_error_to_file(error_data)
        return None
    
    # Process variants
    size_stock = extract_sizes_and_stock(json_data)
    if not size_stock:
        logger.warning(f"No valid variants found in {filepath}")
        return None
    
    # Process common product data once
    common_data = {
        'product_id': f'shn{product_details["baseProduct"]}',
        'gender': 'female' if product_details.get('brickCategory', '').lower() == 'women' else 'male',
        'age_group': ['adult'],
        'age_range': ['18y'],
        'date_of_scraping': datetime.strptime(time_stamp, "%Y%m%d").replace(tzinfo=timezone.utc).isoformat(timespec='milliseconds'),
        'url': WEBSITE_URL.rstrip('/') + product_details['url'],
        'title': product_details['name'],
        'description': None,
        'product_ref_code': product_details['code'],
        'color_name': product_details['code'].split('_')[-1],
        'composition': extract_composition(product_details),
        'origin': next((c['title'].lower() for c in product_details.get('mandatoryInfo', []) 
                      if c.get('key') == 'Country Of Origin'), None),
        'images': extract_images(product_details)
    }
    
    # Process each variant
    results = []
    for item in size_stock:
        color_id_lookup = color_code['color_to_code'].get(common_data['color_name'].lower())
        
        variant_data = {
            **common_data,
            'color_id': f'shn{product_details["baseProduct"]}%{color_id_lookup}' if color_id_lookup else None,
            'color_ref_code': product_details['code'],
            'sku': f'shn{product_details["baseProduct"]}%p{product_details["baseProduct"]}c{color_id_lookup}s{get_size_code(item["size"].lower())}',
            'size_name': item['size'].lower(),
            'size_ref_code': None,
            'price': item['price'],
            'launch_price': item['price'],
            'availability': "in_stock" if item['stock_status'].lower() == 'instock' else "out_of_stock",
            'demand': None
        }
        results.append(variant_data)
    
    return results

# Load color codes
color_code = load_color_codes()

def start_step7():
    # Folder containing RAW_DATA files
    raw_data_dir = f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/RAW_DATA"
    output_path = f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/product_data.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    all_products = []

    for filename in os.listdir(raw_data_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(raw_data_dir, filename)
            products = process_product_file(filepath)
            if products:
                all_products.extend(products)

    if all_products:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(all_products, f, indent=2)
            logger.info(f"Successfully processed {len(all_products)} variants from {len(os.listdir(raw_data_dir))} files")
        except Exception as e:
            logger.error(f"Failed to save output: {str(e)}")
    else:
        logger.warning("No valid product data found to save.")

    return True

if __name__ == "__main__":
    start_step7()