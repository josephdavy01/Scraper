import os
import json
import traceback
import re
from datetime import datetime
import pymongo
from bs4 import BeautifulSoup
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def parse_launch_date(date_string):
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d', '%Y-%m-%d %H:%M:%S.%f'
    ]
    for f in formats:
        try:
            return datetime.strptime(date_string, f)
        except Exception:
            continue
    logger.error(f"Failed to parse date: {date_string}")
    return None

def get_images(images_list):
    image_list = []
    for i, img in enumerate(images_list):
        image_style = "n_f_f_c" if i == 0 else "s0"
        image_list.append({"url": img, "image_style": image_style})
    return image_list

def extract_currency_from_url(product_url):
    if not product_url:
        return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(product_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        meta_tag = soup.find('meta', property='og:price:currency')
        if meta_tag and meta_tag.get('content'):
            return meta_tag.get('content')
    except Exception as e:
        logger.error(f"Error extracting currency from {product_url}: {e}")
    return None

def extract_description(html_desc):
    if not html_desc:
        return ""
    start_marker = "Fabric/Material"
    start_idx = html_desc.find(start_marker)
    if start_idx == -1:
        return ""
    return html_desc[start_idx:]

def extract_composition(html_desc):
    if not html_desc:
        return ""
    start_marker = "Fabric/Material"
    end_marker = "Care Info"
    start_idx = html_desc.find(start_marker) + len(start_marker)
    if start_idx == -1:
        return ""
    end_idx = html_desc.find(end_marker, start_idx)
    if end_idx == -1:
        return ""
    return html_desc[start_idx:end_idx].strip()

def extract_gender_from_json(json_data):
    gender = str(json_data.get('gender', '')).lower().strip()
    if gender in ['men', 'male', 'm']:
        return 'male'
    elif gender in ['women', 'female', 'w', 'ladies']:
        return 'female'
    elif gender in ['kids', 'children', 'boys', 'girls']:
        return 'kids'
    text_blob = (json_data.get('name', '') + " " + json_data.get('description', '')).lower()
    if any(word in text_blob for word in ['men ', "men's", 'male']):
        return 'male'
    if any(word in text_blob for word in ['women ', "women's", 'female', 'ladies']):
        return 'female'
    if any(word in text_blob for word in ['kid', 'child', 'children', 'boy', 'girl']):
        return 'kids'
    return 'unisex'

def convert_to_numeric(value, field_name):
    if value is None:
        logger.error(f"Field {field_name} is None")
        return None
    try:
        cleaned_value = str(value).replace(',', '')
        return float(cleaned_value)
    except (ValueError, TypeError) as e:
        logger.error(f"Field {field_name} contains non-numeric value: {value}")
        return None

def map_availability(value, field_name):
    if isinstance(value, bool):
        return "in_stock" if value else "out_of_stock"
    if isinstance(value, str):
        value = value.lower()
        if 'instock' in value:
            return "in_stock"
        if 'outofstock' in value:
            return "out_of_stock"
    logger.error(f"Field {field_name} contains invalid value: {value}")
    return "out_of_stock"

def normalize_size(size_str):
    """
    Normalize size values.
    Example: "067[S]" -> "S"
             "073[L]" -> "L"
             "064[XS]" -> "XS"
             "M" -> "M"
    """
    if not size_str:
        return None
    match = re.search(r"\[(.*?)\]", size_str)
    if match:
        return match.group(1).strip()
    return size_str.strip()

def map_custom_product_record(product_data, today_str, sku_value, size_name, availability, currency=None, color_id_map=None):
    pid_raw = str(product_data.get("product_id", "")) or ""
    product_id = f'8sc{pid_raw}'
    gender_std = extract_gender_from_json(product_data)
    if gender_std == 'kids':
        age_group = ['kids']
        age_range = ['1y', '17y']
    else:
        age_group = ['adult']
        age_range = ['18y']
    brand = product_data.get("brand", {}).get("name", "Unknown").lower()
    price = convert_to_numeric(product_data.get("offers", {}).get("price"), "price")
    launch_price = convert_to_numeric(product_data.get("prices", {}).get("default_price"), "launch_price")
    availability_str = map_availability(availability, "availability")
    html_description = product_data.get('description', '')
    description = extract_description(html_description)
    compositions = extract_composition(html_description)
    composition = compositions if compositions else None
    product_url = product_data.get('offers', {}).get('url', '')
    color_name = product_data.get('available_colors', [''])[0].lower()
    color_id = product_data.get('sku', '')
    new_color_id = color_id_map.get(color_name, None) if color_id_map else None
    size_specific_sku = f'{product_id}%p{pid_raw}c{new_color_id}s{size_name}'.replace(' ', '')
    # Assign new color ID from color_id_map if available
    return {
        'product_id': product_id,
        'gender': gender_std,
        'age_group': age_group,
        'age_range': age_range,
        'date_of_scraping': parse_launch_date(today_str),
        'url': product_url,
        'title': product_data.get('name', '').lower(),
        'description': description,
        'product_ref_code': color_id,
        'color_id': f'{product_id}%{new_color_id}',
        'color_name': color_name,
        'color_ref_code': None,
        'sku': size_specific_sku,
        'size_name': size_name,   # normalized size saved here
        'size_ref_code': None,
        'price': price,
        'launch_price': launch_price,
        'availability': availability_str,
        'demand': None,
        'composition': composition,
        'origin': None,
        'images': get_images(product_data.get('images', [])),
    }

def create_records_from_json(today_str, json_data, color_id_map):
    records = []
    product_base = {
        'sku': json_data.get('sku'),
        'name': json_data.get('name'),
        'description': json_data.get('description'),
        'brand': json_data.get('brand'),
        'prices': json_data.get('prices'),
        'available_colors': json_data.get('available_colors', []),
        'available_sizes': json_data.get('available_sizes', []),
        'images': json_data.get('images', []),
        'offers': json_data.get('offers', {}),
        'gender': json_data.get('gender', ''),
        'product_id': json_data.get('product_id', '')
    }
    
    valid_sizes = {"XS", "S", "M", "L", "XL", "XXS", "XXL", "2XL", "3XL", "4XL", "5XL", "6XL", "M/L"}
    sizes = product_base.get('available_sizes', [])
    
    # Normalize sizes (handle cases like "067[S]")
    normalized_sizes = [normalize_size(size) for size in sizes if size]
    
    # Check if all normalized sizes are valid
    all_sizes_valid = all(size in valid_sizes for size in normalized_sizes)
    if not all_sizes_valid:
        logger.warning(f"Skipping product {product_base['sku']} due to invalid sizes: {normalized_sizes}")
        return records

    for size in normalized_sizes:
        availability = product_base.get('offers', {}).get('availability', '')
        rec = map_custom_product_record(
            product_base,
            today_str,
            product_base['sku'],
            size,
            availability=availability,
            currency=product_base.get('currency'),
            color_id_map=color_id_map
        )
        if rec['price'] is None or rec['launch_price'] is None:
            logger.error(f"Skipping record for SKU {rec['sku']} due to invalid price or launch_price")
            continue
        if rec['availability'] not in ("in_stock", "out_of_stock"):
            logger.error(f"Skipping record for SKU {rec['sku']} due to invalid availability: {rec['availability']}")
            continue
        records.append(rec)
    return records

def get_distinct_colors(base_path):
    colors = set()
    if not os.path.exists(base_path):
        logger.error(f"Base path does not exist: {base_path}")
        return colors
    for root, _, files in os.walk(base_path):
        for file_name in files:
            if file_name.endswith('.json'):
                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    color_name = json_data.get('available_colors', [''])[0].lower()
                    if color_name:
                        colors.add(color_name)
                        logger.info(f"Found color in {file_path}: {color_name}")
                    else:
                        logger.warning(f"No valid color in {file_path}: {json_data.get('available_colors', [])}")
                except json.JSONDecodeError as e:
                    logger.error(f"Error reading JSON file {file_path}: {e}")
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
    return colors

def process_json_files_recursive(today_str, country, collection, base_path):
    # Step 1: Collect distinct colors and generate color IDs
    colors = get_distinct_colors(base_path)
    if not colors:
        logger.warning("No distinct colors found in JSON files.")
    color_id_map = {color: f"{i+1:03d}" for i, color in enumerate(sorted(colors))}
    logger.info(f"Color ID Mapping: {color_id_map}")
    
    # Step 2: Save color ID mapping to a JSON file
    output_file = "color_id_mapping.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(color_id_map, f, indent=4)
    logger.info(f"Color ID mapping saved to {output_file}")

    # Step 3: Process JSON files and insert records with new color IDs
    if not os.path.exists(base_path):
        logger.error(f"Path not found: {base_path}")
        return
    for root, _, files in os.walk(base_path):
        for file_name in files:
            if file_name.endswith('.json'):
                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    records = create_records_from_json(today_str, json_data, color_id_map)
                    if records:
                        try:
                            collection.insert_many(records)
                            logger.info(f"Inserted {len(records)} records from {file_path}")
                        except Exception as e:
                            logger.error(f"Error inserting records from {file_path}: {e}")
                            traceback.print_exc()
                    else:
                        logger.warning(f"No valid records to insert from {file_path}")
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    traceback.print_exc()
def main():
    MONGODB_URI = "mongodb://localhost:27017"  # Replace with your MongoDB URI
    try:
        client = pymongo.MongoClient(MONGODB_URI)
        db = client['tg_analytics']  # Replace with your database name
        collection = db['crawler_sink_8sec_south_korea']  # Replace with your collection name
        country = 'korea' 
        
        dates = os.listdir(os.path.join(country, "Data"))

        for today_str in dates:

        # today_str = datetime.today().strftime("%Y-%m-%d")
        # today_str = '2025-11-25'
         # Based on KRW currency and KOODING.com
            base_path = os.path.join(country, 'Data',today_str, 'Json_data')
            process_json_files_recursive(today_str, country, collection, base_path)
            logger.info("Load complete.")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        traceback.print_exc()
    finally:
        client.close()

if __name__ == "__main__":
    main()