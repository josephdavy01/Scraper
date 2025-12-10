import os
import re
import json
import pymongo
import traceback
from datetime import date, datetime, timezone

EXCLUDED_KEYWORDS = [
    "toy", "cap", "sock", "footsie", "backpack", "scarf", "beanie",
    "glove", "mitten", "umbrella", "bag", "hat", "belt",
    "sneaker", "shoe", "boot"
]
def clean_composition(composition):
    new_composition = composition
    if 'Delivery Date' in composition or 'Gentle Machine' in composition:
        return None
    if 'CAUTION' in new_composition:
        new_composition = new_composition.split('CAUTION')[0].strip()
    if 'Imported' in new_composition:
        new_composition = new_composition.replace('Imported', '')
    if '<br>' in new_composition:
        new_composition = new_composition.replace('<br>', '')
    if '/ Exclusive of Decoration' in new_composition:
        new_composition = new_composition.replace('/ Exclusive of Decoration', '')
    if ', Exclusive of Decoration' in new_composition:
        new_composition = new_composition.replace(', Exclusive of Decoration', '')
    if 'time.' in new_composition:
        new_composition = new_composition.split('time.')[-1].strip()
    if ']' in new_composition:
        new_composition = new_composition.split(']')[-1].split('[')[0].strip()
    if ':' in new_composition:
        fisrt_part = new_composition.split(':')[0].strip().split(' ')[-1]
        if fisrt_part.isdigit():
            new_composition = new_composition.split(':')[-1]
            if ':' in new_composition:
                new_composition = new_composition.split(':')[0][:-6]
 
    if 'Base:' in new_composition:
        new_composition = 'Base: ' + new_composition.split('Base:')[-1].split('/')[0].strip()
    elif 'Body:' in new_composition:
        new_composition = 'Body: ' + new_composition.split('Body:')[-1].split('/')[0].strip()
    elif 'Shell:' in new_composition:
        new_composition = 'Shell: ' + new_composition.split('Shell:')[-1].split('/')[0].strip()
   
    return new_composition

def is_excluded_product(title: str) -> bool:
    if not title:
        return False
    title_lower = title.lower()
    for word in EXCLUDED_KEYWORDS:
        pattern = r'\b' + re.escape(word) + r's?\b'
        if re.search(pattern, title_lower):
            return True
    return False

def remap_gender(json_data):
    gender = str(json_data.get('gender', '')).lower().strip()
    if gender == "women":
        return 'female'
    elif gender == "men":
        return 'male'
    elif gender in ["kids", "baby"]:
        return None 
    else:
        return 'unisex'

def clean_product_id(raw_id: str) -> str:
    if not raw_id:
        return ''
    match = re.match(r"[A-Za-z]*([0-9]+)", raw_id)
    if match:
        return match.group(1)
    return raw_id

def clean_and_combine_description(json_data):
    cleaned_desc = ""   

    desc = json_data.get("description", "")
    if desc:
        desc_parts = [part.strip(" -") for part in desc.split(".") if part.strip()]
        cleaned_desc = ". ".join(desc_parts)

    features = json_data.get("features", [])
    if features:
        features_str = " | ".join([f.strip(" -") for f in features])
        if cleaned_desc:
            cleaned_desc += " | " + features_str
        else:
            cleaned_desc = features_str

    return cleaned_desc

def get_image_style(image_list):
    return [{"url": img, "image_style": "s0"} for img in image_list]

def extract_prices(json_data):
    def safe_get(price_obj):
        if isinstance(price_obj, dict):
            return price_obj.get("value")
        elif isinstance(price_obj, (int, float)):
            return price_obj
        elif isinstance(price_obj, str):
            num = re.findall(r"\d+\.?\d*", price_obj)
            return float(num[0]) if num else None
        return None
    return {
        "price": safe_get(json_data.get("prices", {}).get("price", json_data.get("price"))),
        "launch_price": safe_get(json_data.get("prices", {}).get("launch_price", json_data.get("launch_price")))
    }

def sanitize_size(size_name: str) -> str:
    return re.sub(r'[^A-Za-z0-9]', '', size_name).upper()

def get_age_group(gender):
    return ["adult"] if gender in ["male", "female", "unisex"] else []

def get_age_range(gender):
    return ["18y"] if gender in ["male", "female", "unisex"] else []

def parse_launch_date(date_string):
    format_string_with_ms = '%Y-%m-%dT%H:%M:%S.%fZ'
    format_string_without_ms = '%Y-%m-%dT%H:%M:%SZ'
    format_string_date_only = '%Y-%m-%d'
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            return datetime.strptime(date_string, format_string_date_only)

def create_individual_json(today_str, json_data):
    all_products = []
    if not json_data or not isinstance(json_data, dict):
        return []
    gender = remap_gender(json_data)
    if not gender:
        print(f"Skipping product {json_data.get('product_id')} - kids/baby")
        return []
    prdt_id = clean_product_id(json_data.get('product_id', ''))
    product_id = 'uni' + prdt_id
    name = json_data.get('title', '').lower()
    url = json_data.get('variant_url', '')
    descriptions = clean_and_combine_description(json_data)
    cid = json_data.get('color_id', '')
    color_name = " ".join(json_data.get('color_name', '').split(" ")[1:]).strip().lower()
    images = get_image_style(json_data.get('images', []))
    prices = extract_prices(json_data)
    
    origin_val = json_data.get("origin")
    if origin_val:
        origin = origin_val.split(",")[0].strip().lower()
    else:
        origin = None

    composition = json_data.get("composition")
    if composition:
        cleaned_composition = clean_composition(composition)

    sizes = json_data.get("sizes", [])
    if not sizes:
        return []
    for size_obj in sizes:
        size_name = size_obj.get("size_name", "").strip()
        if not size_name:
            continue
        availability = size_obj.get("availability", "").lower()
        safe_size = sanitize_size(size_name)
        size_id = size_obj.get("size_id")
        size_specific_sku = f"{product_id}%p{prdt_id}c{cid}s{size_id}"
        if prices["price"] is None:
            print(f"Skipping {product_id} size {size_name} - price is null")
            continue
        entry = {
            "product_id": product_id,
            "sub_brand": None,
            "gender": gender,
            "age_group": get_age_group(gender),
            "age_range": get_age_range(gender),
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": name,
            "description": descriptions,
            "product_ref_code": None,
            "color_id": f'{product_id}%{cid}',
            "color_name": color_name,
            "color_ref_code": cid,
            "sku": size_specific_sku,
            "size_name": size_name,
            "size_ref_code": size_id,
            "price": prices["price"],
            "launch_price": prices["launch_price"],
            "availability": availability,
            "demand": None,
            "origin": origin,
            "composition": cleaned_composition,
            "images": images
        }
        all_products.append(entry)
    return all_products

def get_folders(path, exclude=None):
    if exclude is None:
        exclude = []
    if not os.path.exists(path):
        return []
    return [f for f in os.listdir(path) if f not in exclude and '.json' not in f]

def process_jsons(today_str, country, collection):
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = get_folders(gender_folder)
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder)
        for category in categories:
            file_folder = os.path.join(category_folder, category)
            if not os.path.exists(file_folder):
                continue
            for file_name in os.listdir(file_folder):
                file_path = os.path.join(file_folder, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    skus = create_individual_json(today_str, data)
                    if skus:
                        collection.insert_many(skus)
                        for sku in skus:
                            print(f'Product_id: {sku["product_id"]}, SKU: {sku["sku"]}')
                    else:
                        print(f"Skipping {file_name} - not apparel or missing data")
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client['tg_analytics']
    countries = ['UK']
    for country in countries:
        collection = db[f'crawler_sink_uniqlo_{country.lower()}']
        print(f"Processing {country} apparel...")
        data_path = os.path.join(country, 'Data')
        if not os.path.exists(data_path):
            continue
        for today_subfolder in os.listdir(data_path):
            process_jsons(today_subfolder, country, collection)
        print(f"Apparel data loading for {country} completed!")
    client.close()
