import os
import re
import json
from datetime import date, datetime
import traceback
import pymongo
from pymongo.errors import BulkWriteError


def parse_launch_date(date_string):
    format_string_with_ms = '%Y-%m-%dT%H:%M:%S.%fZ'
    format_string_without_ms = '%Y-%m-%dT%H:%M:%SZ'
    format_string_date_only = '%Y-%m-%d'
    format_string_with_ms_no_tz = '%Y-%m-%d %H:%M:%S.%f'
    
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            try:
                return datetime.strptime(date_string, format_string_date_only)
            except ValueError:
                return datetime.strptime(date_string, format_string_with_ms_no_tz)


# ----------------- Mongo -----------------

def connect_to_mongodb(connection_string, db_name, collection_name_prefix, country, date_str):
    """Connect to MongoDB and return the collection for the specified country and date."""
    try:
        client = pymongo.MongoClient(connection_string)
        db = client[db_name]
        collection = db[f'{collection_name_prefix}_{country.lower()}_footwear']
        print(f" Connected to MongoDB collection: {collection.name}")
        return client, db, collection
    except Exception as e:
        print(f" Error connecting to MongoDB: {e}")
        traceback.print_exc()
        return None, None, None


# ----------------- Normalizers -----------------

def remap_gender(product_data):
    gender = product_data.get('Gender', '')
    if not gender:
        return 'unisex'
    g = str(gender).lower()
    if g in ['women', 'woman', 'female', 'girls', 'girl']:
        return 'female'
    if g in ['men', 'man', 'male', 'boys', 'boy']:
        return 'male'
    return 'unisex'


def get_age_group(product_data):
    sizes = product_data.get('Sizes', []) or []
    age_groups = set(size.get('Age Group', '').strip().lower() for size in sizes if size.get('Age Group'))
    
    if not age_groups:
        return ['adult']
    
    for age_group in age_groups:
        if 'new born' in age_group or '0-6 months' in age_group:
            return ['kids']
        if 'baby' in age_group or '7-24 months' in age_group or '6-24 months' in age_group:
            return ['kids']
        if 'little kids' in age_group or '4-8 years old' in age_group:
            return ['kids']
        if 'big kids' in age_group or '8-10 years old' in age_group or '8-12 years' in age_group:
            return ['kids']
        if 'teen' in age_group or '13-17 years old' in age_group:
            return ['kids']
    
    return ['adult']


def get_age_range(product_data):
    sizes = product_data.get('Sizes', []) or []
    age_groups = set(size.get('Age Group', '').strip().lower() for size in sizes if size.get('Age Group'))
    
    if not age_groups:
        return ['18y']
    
    for age_group in age_groups:
        if 'little kids (4-8 years old)' in age_group:
            return ['1y', '17y']
        if 'big kids (8-10 years old)' in age_group:
            return ['1y', '17y']
        if 'toddlers' in age_group:
            return ['0y', '17y']
    
    return ['18y']


def remap_occasion(occasion):
    if not occasion:
        return 'casual'
    occ = str(occasion).lower()
    mapping = {
        'casual': 'casual',
        'athletic': 'athletic',
        'running': 'running',
        'walking': 'walking',
        'training': 'training',
        'lifestyle': 'lifestyle',
        'sport': 'sport'
    }
    return mapping.get(occ, 'casual')


# ----------------- Feature Extraction -----------------

def extract_materials(features):
    result = {"sole_material": None, "upper_material": None, "lining_material": None}
    if not features or not isinstance(features, list):
        return result

    for raw in features:
        line = str(raw).strip()
        low = line.lower()

        def val_after_colon(s):
            if ":" in s:
                value = s.split(":", 1)[-1].strip()
                for prefix in ["outsole", "upper", "lining", "insole", "materials"]:
                    if value.lower().startswith(prefix):
                        value = value[len(prefix):].strip(" :,")
                return value
            return s.strip()

        if ("outsole" in low) and ("midsole" not in low):
            result["sole_material"] = val_after_colon(line).lower()
        elif "upper" in low:
            result["upper_material"] = val_after_colon(line).lower()
        elif "lining" in low or "insole" in low:
            result["lining_material"] = val_after_colon(line).lower()

    return result


def extract_other_features(features):
    heel_type = None
    toe_shape = None
    closure_type = None
    heel_to_toe_drop = None

    if not features or not isinstance(features, list):
        return heel_type, toe_shape, closure_type, heel_to_toe_drop

    for raw in features:
        line = str(raw).strip()
        low = line.lower()

        def val_after_colon(s):
            return s.split(":", 1)[-1].strip() if ":" in s else s.strip()

        if "heel" in low:
            heel_type = val_after_colon(line)
        if "toe" in low:
            toe_shape = val_after_colon(line)
        if "closure" in low or "lace-up" in low or "slip" in low:
            closure_type = val_after_colon(line)
        if "drop" in low:
            heel_to_toe_drop = val_after_colon(line)

    return heel_type, toe_shape, closure_type, heel_to_toe_drop


# ----------------- Size Filter -----------------

def is_valid_footwear_size(size_name):
    if size_name is None:
        return False
    s = str(size_name).strip()
    return bool(re.fullmatch(r"\d+(\.\d)?", s))


# ----------------- Image Processor -----------------

def get_images(images):
    image_list = []
    total_images = len(images)

    for idx, image in enumerate(images):
        if not image:
            continue
        image_style = 's0'
        if total_images >= 5 and idx == total_images - 2:
            image_style = 'n_f_f_c'
        image_list.append({
            "url": image,
            "image_style": image_style
        })

    return image_list


# ----------------- SKU Builder -----------------

def parse_price_to_float(price_str):
    if not price_str:
        return 0.0
    s = str(price_str)
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else 0.0


def create_individual_sku(today_str, product_data, country):
    all_skus = []
    try:
        if isinstance(product_data, str):
            try:
                product_data = json.loads(product_data)
            except json.JSONDecodeError:
                return []
        if not isinstance(product_data, dict):
            return []

        pid_raw = product_data.get("Product Id", "") or product_data.get("Product ID", "")
        pid = f'skr{pid_raw}'

        color_id = product_data.get('Color ID') or product_data.get('Color Id', '')
        cid = product_data.get('Color Reference Code', color_id) or ''
        sku_base = product_data.get('SKU as per the website', pid)

        gender_std = remap_gender(product_data)
        age_group = get_age_group(product_data)
        age_range = get_age_range(product_data)

        features = product_data.get('Features', [])
        materials = extract_materials(features)
        heel_type, toe_shape, closure_type, heel_to_toe_drop = extract_other_features(features)
        occasion_norm = remap_occasion(product_data.get('Occasion', ''))

        price = parse_price_to_float(product_data.get('Price', ''))
        if not price or price == 0:
            return
        launch_price = parse_price_to_float(product_data.get('Launch Price', ''))

        # Country -> Size Prefix mapping
        country_size_prefix = {
            "US": "US",
            "UK": "UK",
            "India": "IN",
            "Canada": "CA",
            "Saudi": "SA",
            "Spain": "EU",
            "Turkey": "EU",
            "UAE": "AE"
        }
        prefix = country_size_prefix.get(country, country.upper())

        sizes = product_data.get('Sizes', []) or []
        for size in sizes:
            size_name_raw = (size.get('Size name', '') or '').strip()
            size_ref = (size.get('Size Reference Code', '') or '').strip()

            availability_raw = size.get('Availability') or size.get('Availablity', '')
            availability = 'in_stock' if str(availability_raw).strip().lower() == 'in stock' else 'out_of_stock'

            if not is_valid_footwear_size(size_name_raw):
                continue

            # Add country prefix
            size_name = f"{prefix} {size_name_raw}"

            sku_value = f'{pid}%p{pid_raw}c{cid}s{size_name}'
            cids = f'{pid}%{cid}'

            sku_entry = {
                'product_id': pid,
                'gender': gender_std,
                'age_group': age_group,
                'age_range': age_range,
                'date_of_scraping': parse_launch_date(today_str),
                'url': product_data.get('Product Url', ''),
                'title': product_data.get('Title', '').lower(),
                'sub_brand': None,
                'description': product_data.get('Description', ''),
                'product_ref_code': product_data.get('Product Reference Code', pid_raw) or pid_raw,
                'color_id': cids,
                'color_name': (product_data.get('Color Name', '') or '').lower(),
                'color_ref_code': color_id,
                'sku': sku_value,
                'size_name': size_name,
                'size_ref_code': size_ref,
                'price': price,
                'launch_price': launch_price,
                'availability': availability,
                'sole_material': materials["sole_material"],
                'upper_material': materials["upper_material"],
                'occasion': occasion_norm,
                'closure_type': closure_type,
                'toe_shape': toe_shape,
                'heel_type': None,
                'weight': None,
                'heel_to_toe_drop': heel_to_toe_drop,
                'origin': None,
                'images': get_images(product_data.get('Images', []) or []),
                'brand': (product_data.get('Brand', 'Skechers') or 'Skechers').lower(),
            }
            all_skus.append(sku_entry)

        return all_skus

    except Exception as e:
        print(f" Error creating SKU: {e}")
        traceback.print_exc()
        return []


# ----------------- JSON Ingestion -----------------

def process_jsons(today_str, country, collection):
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    if not os.path.exists(gender_folder):
        print(f" Folder not found: {gender_folder}")
        return 0

    total_products = 0

    for root, _, files in os.walk(gender_folder):
        for file in files:
            if not file.endswith('.json'):
                continue
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as jf:
                    data = json.load(jf)

                if isinstance(data, dict) and any(k in data for k in ('Product Id', 'Title', 'Product Url')):
                    products = [data]
                elif isinstance(data, list):
                    products = [p for p in data if isinstance(p, dict)]
                elif isinstance(data, dict):
                    products = [p for p in data.values() if isinstance(p, dict)]
                else:
                    continue

                for product in products:
                    if not isinstance(product, dict):
                        continue
                    skus = create_individual_sku(today_str, product, country)
                    if skus:
                        try:
                            collection.insert_many(skus, ordered=False)
                            total_products += 1
                        except BulkWriteError as bwe:
                            print(f" Bulk write error for {file_path}: {bwe.details}")

            except Exception as e:
                print(f" Error processing {file_path}: {e}")
                traceback.print_exc()

    return total_products


# ----------------- Main -----------------

if __name__ == "__main__":
    countries = {
        'Canada': 'ca',
        'India': 'in',
        'Saudi': 'sa/en',
        'Spain': 'es/en',
        'Turkey': 'tr/en',
        'UAE': 'ae',
        'UK': 'gb',
        'US': 'us'
    }

    # 🔧 Config placeholders
    connection_string = "mongodb://localhost:27017"  # Your MongoDB URI
    db_name = "tg_analytics"            # Your DB name
    collection_name_prefix = "crawler_sink_skechers"

    
    today_str = date.today().strftime('%Y-%m-%d')  
    # today_str = '2025-12-03' 
    countries_to_process = ["UK", "USA"]

    for country in countries_to_process:
        print(f"\n Processing {country} ...")
        client, db, collection = connect_to_mongodb(connection_string, db_name, collection_name_prefix, country, today_str)
        if collection is None:
            continue

        process_jsons(today_str, country, collection)
        if client:
            client.close()
            print(f" Closed MongoDB connection for {country}")
