import logging
import os
import json
import traceback
from datetime import datetime
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Configuration for each country
COUNTRY_CONFIG = {
    'USA': {
        'base_url': 'https://kith.com',
        'image_style_index': 1
    },
    'UK': {
        'base_url': 'https://eu.kith.com',
        'image_style_index': 0
    }
}

def parse_launch_date(date_string):
    """Parses a date string from multiple possible formats."""
    formats_to_try = [
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d',
        '%m-%d-%Y'
    ]
    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    logging.error(f"Could not parse date: {date_string}")
    return None

def is_apparel(product_type):
    pt = product_type.lower() if product_type else ''
    return any(keyword in pt for keyword in ['short sleeve tees', 'shorts', 'button up shirts', 'pants', 'hoodies', 'crewnecks', 'polo shirts', 'sweatpants', 'long sleeve tees', 'tank tops', 'active shorts', 'jackets', 'track jackets', 'mini skirts', 'track pants', 'bomber jackets', 'tees', 'coaches jackets', 'skirts', 'rugby shirts', 'dresses', 'cargo pants', 'trousers', 'mini dresses', 'jeans', 'maxi dresses', 'cardigans', 'blazers', 'maxi skirts', 'vests', 'outerwear', 'rompers', 'denim jackets', 'leggings', 'cargo shorts', 'coats', 'gi shirts', 'crewneck sweaters', 'undershirts', 'baby bodysuits', 'shirts', 'shirt jackets', 'fleece jackets', 'short sleeve henleys', 'varsity jackets', 'gi jackets', 'sweatshirts', 'suits', 'bodysuits', 'leather jackets', 'polos', 'short sleeve tops', 'trench coats', 'baby bodysuit'])

def get_image_style(image_list, country):
    """Gets image styles, applying country-specific logic."""
    config = COUNTRY_CONFIG.get(country, {})
    image_style_index = config.get('image_style_index', 1)

    images = []
    for index, image in enumerate(image_list):
        if isinstance(image, str):
            if image.startswith("//"):
                image = "https:" + image
            
            image_style = 's0'
            if 'FRONT' in image.upper() or index == image_style_index:
                image_style = 'n_f_f_c'
            
            images.append({"url": image, "image_style": image_style})
    return images

def remove_html(description):
    """Removes HTML tags and entities from a string."""
    if not description:
        return ""
    clean_desc = re.sub(r'<[^>]+>', '', description)
    clean_desc = ' '.join(clean_desc.split())
    clean_desc = clean_desc.replace('&nbsp;', ' ').replace('&amp;', '&')
    return clean_desc.strip()

def get_gender_from_vendor(vendor, tags=None):
    """Determines gender from vendor and tags."""
    if "Women" in vendor:
        return "female"
    if "Kids" in vendor:
        return "kids"
    if vendor == "Kith":
        return "male"
    
    if tags:
        tags_lower = [tag.lower() for tag in tags]
        if any(tag in tags_lower for tag in ['kids', 'children', 'child']):
            return "kids"
        if any(tag in tags_lower for tag in ['women', 'womens', 'female']):
            return "female"
        if any(tag in tags_lower for tag in ['men', 'mens', 'male']):
            return "male"
    
    return "unisex"

def get_age_group(gender):
    return ["kids"] if gender == "kids" else ["adult"]

def get_age_range(gender):
    return ['1y', '17y'] if gender == "kids" else ["18y"]

def extract_color_from_title(title):
    """Extracts clean title and color from the product title."""
    parts = title.split(" - ")
    if len(parts) >= 2:
        clean_title = parts[0].strip().lower()
        color_part = parts[-1].strip().lower()
        return clean_title, color_part
    
    clean_title = title.strip().lower()
    return clean_title, ""

def get_pid(clean_pid, pdict):
    """Gets the mapped PID."""
    return pdict.get(clean_pid, '0000000')

def create_individual_json(date_dir, json_data, file_name, pdict, cdict, country):
    """Creates a standardized JSON object for a single product."""
    config = COUNTRY_CONFIG.get(country, {})
    base_url = config.get('base_url', 'https://kith.com')

    product_json = json_data.get("product_json", {})
    if not product_json:
        logging.warning(f"No product_json found in {file_name}")
        return []

    vendor = product_json.get("vendor", "").strip()
    allowed_vendors = ["Kith", "Kith Kids", "Kith Women"]
    if vendor not in allowed_vendors:
        logging.info(f"Skipping file {file_name} - vendor '{vendor}' not in allowed list")
        return []

    if not is_apparel(product_json.get("type", "")):
        logging.info(f"Skipping file {file_name} - category '{product_json.get('type', '')}' not apparel")
        return []

    all_products = []
    
    handle = product_json.get("handle", "")
    original_title = product_json.get("title", "")
    clean_title, color_name = extract_color_from_title(original_title)
    
    raw_description = product_json.get("description", "").replace("&lt;", "<").replace("&gt;", ">").strip()
    content = product_json.get('content', '').strip()
    
    description = remove_html(raw_description)
    composition = remove_html(content)
    
    mapped_pid = get_pid(clean_title, pdict)
    mapped_cid = cdict.get(color_name, '000')
    pid = "kit" + mapped_pid
    
    gender = get_gender_from_vendor(vendor, product_json.get("tags", []))
    
    price = product_json.get("price", 0)
    launch_price = product_json.get("compare_at_price")
    if launch_price is None:
        launch_price = price
    
    price = float(price / 100.0)
    launch_price = float(launch_price / 100.0)
    
    url = f"{base_url}/products/{handle}"
    scraping_date = parse_launch_date(date_dir)
    scraping_date_str = scraping_date.isoformat() if scraping_date else date_dir

    for variant in product_json.get("variants", []):
        entry = {
            "product_id": pid,
            "gender": gender,
            "age_group": get_age_group(gender),
            "age_range": get_age_range(gender),
            "date_of_scraping": scraping_date_str,
            "url": url,
            "title": clean_title.lower(),
            "description": description,
            "product_ref_code": handle,
            "color_id": f'{pid}%{mapped_cid}',
            "color_name": color_name,
            "color_ref_code": None,
            "sku": f'{pid}%{variant.get("sku", "")}',
            "size_name": variant.get("title", ""),
            "size_ref_code": None,
            "price": price,
            "launch_price": launch_price,
            "availability": "in_stock" if variant.get("available", False) else "out_of_stock",
            "demand": None,
            "composition": composition,
            "origin": None,
            "images": get_image_style(product_json.get("images", []), country)
        }
        all_products.append(entry)

    return all_products

def process_jsons(date_dir, country, pdict, cdict):
    """Processes all raw JSON files for a given country and date."""
    json_data_path = os.path.join(country, date_dir, 'Json_data')
    if not os.path.exists(json_data_path):
        logging.warning(f"Directory {json_data_path} does not exist.")
        return []

    all_country_products = []
    for root, _, files in os.walk(json_data_path):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                logging.info(f"Processing file: {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        json_data = json.load(json_file)
                    
                    product_list = create_individual_json(date_dir, json_data, file, pdict, cdict, country)
                    if product_list:
                        all_country_products.extend(product_list)
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON in {file_path}: {e}")
                except Exception as e:
                    logging.error(f"Error processing {file_path}: {e}")
                    traceback.print_exc()
    
    return all_country_products

def process_apparel(countries, today_date, re_run=False):
    """Main function to process apparel data for specified countries."""
    pid_path = 'kith_pid_remapping.json'
    cid_path = 'kith_cid_remapping.json'

    pdict = {}
    if os.path.exists(pid_path):
        with open(pid_path, 'r') as json_file:
            pdict = json.load(json_file)

    cdict = {}
    if os.path.exists(cid_path):
        with open(cid_path, 'r') as json_file:
            cdict = json.load(json_file)

    for country in countries:
        logging.info(f"Processing apparel for {country}/{today_date}")
        output_dir = os.path.join(country, today_date, 'Data')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f'{country}_data_apparel.json')

        if not re_run and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logging.info(f"Apparel data for {country} already exists and is not empty. Skipping.")
            continue

        all_products = process_jsons(today_date, country, pdict, cdict)
        
        if all_products:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(all_products, f, indent=4)
            logging.info(f"Successfully saved {len(all_products)} apparel products to {output_path}")
        else:
            logging.warning(f"No apparel products found for {country} on {today_date}")

if __name__ == "__main__":
    TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
    TODAY_DATE = '2025-11-24'
    COUNTRIES = ['USA', 'UK']
    
    process_apparel(COUNTRIES, TODAY_DATE, re_run=False)
    
    print("----------------------Apparel processing completed successfully----------------------")
