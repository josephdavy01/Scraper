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
        collection = db[f'{collection_name_prefix}_{country.lower()}']
        print(f" Connected to MongoDB collection: {collection.name}")
        return client, db, collection
    except Exception as e:
        print(f" Error connecting to MongoDB: {e}")
        traceback.print_exc()
        return None, None, None


# ----------------- Normalizers -----------------

def remap_gender(gender):
    """Remap gender to standardized values."""
    if not gender:
        return 'unisex'
    g = str(gender).lower()
    if g in ['women', 'woman', 'female', 'girls', 'girl']:
        return 'female'
    if g in ['men', 'man', 'male', 'boys', 'boy']:
        return 'male'
    if g in ['kids', 'kid']:
        return 'kids'
    return 'unisex'


def get_age_group(gender_std):
    """Determine age group based on gender."""
    return ['kids'] if gender_std == 'kids' else ['adult']


def get_age_range(gender_std):
    """Determine age range based on gender."""
    return ['0y', '17y'] if gender_std == 'kids' else ['18y']


def remap_occasion(occasion):
    """Normalize occasion field."""
    if not occasion:
        return 'casual'
    occ = str(occasion).lower()
    mapping = {
        'casual': 'casual',
        'formal': 'formal',
        'athletic': 'athletic',
        'lifestyle': 'lifestyle',
        'sport': 'sport'
    }
    return mapping.get(occ, 'casual')


# ----------------- Feature Extraction -----------------

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
        collection = db[f'{collection_name_prefix}_{country.lower()}']
        print(f" Connected to MongoDB collection: {collection.name}")
        return client, db, collection
    except Exception as e:
        print(f" Error connecting to MongoDB: {e}")
        traceback.print_exc()
        return None, None, None


# ----------------- Normalizers -----------------

def remap_gender(gender):
    """Remap gender to standardized values."""
    if not gender:
        return 'unisex'
    g = str(gender).lower()
    if g in ['women', 'woman', 'female', 'girls', 'girl']:
        return 'female'
    if g in ['men', 'man', 'male', 'boys', 'boy']:
        return 'male'
    if g in ['kids', 'kid']:
        return 'kids'
    return 'unisex'


def get_age_group(gender_std):
    """Determine age group based on gender."""
    return ['kids'] if gender_std == 'kids' else ['adult']


def get_age_range(gender_std):
    """Determine age range based on gender."""
    return ['0y', '17y'] if gender_std == 'kids' else ['18y']


def remap_occasion(occasion):
    """Normalize occasion field."""
    if not occasion:
        return 'casual'
    occ = str(occasion).lower()
    mapping = {
        'casual': 'casual',
        'formal': 'formal',
        'athletic': 'athletic',
        'lifestyle': 'lifestyle',
        'sport': 'sport'
    }
    return mapping.get(occ, 'casual')


# ----------------- Feature Extraction -----------------

def extract_materials(composition):
    """
    Extract all details from Composition field or Features list, removing prefixes.
    Prioritize Composition; fall back to Features if Composition is 'Not Specified' or empty.
    Always return a single string for DB storage.
    """
    # If composition is a valid string (not empty or 'not specified'), return it directly
    if isinstance(composition, str) and composition.lower() not in ['not specified', '', 'none']:
        return composition.strip()
    
    # If composition is not a list or is empty, return 'None'
    if not isinstance(composition, list) or not composition:
        return 'None'

    # Extract all items and remove prefixes
    cleaned_items = []
    for item in composition:
        cleaned_item = item.split(':', 1)[-1].strip() if ':' in item else item.strip()
        cleaned_items.append(cleaned_item)

    # Join multiple items into a single string (comma-separated)
    return ', '.join(cleaned_items) if cleaned_items else 'None'



# ----------------- Size Filter -----------------

def is_valid_apparel_size(size_name):
    """
    Validate apparel sizes: XS, S, M, L, XL, XXL, 3XL, 3XXL, and their variations (e.g., 'Large', 'X-Large', '3xl', '2xl').
    Exclude numeric sizes (e.g., '2', '3', '4', '2.0').
    """
    if size_name is None:
        return False
    
    # Convert to string, strip whitespace, and convert to lowercase for consistent comparison
    s = str(size_name).strip().lower()
    
    # Define valid apparel sizes (lowercase for matching)
    valid_sizes = [
        'xs', 's','m' , 'l', 'xl', 'xxl', '3xl', '3xxl',
        'x-small', 'small', 'medium', 'large', 'x-large', 'xx-large',
        'extra small', 'extra-small', 
        'extra large', 'extra-large',
        'double extra large', 'double-extra-large',
        'triple extra large', 'triple-extra-large'
    ]
    
    # Check if the size is purely numeric or a decimal (e.g., '2', '3', '2.0')
    if s.replace('.', '').isdigit():
        return False
    
    # Return True if the size is in valid_sizes
    return s in valid_sizes
# ----------------- SKU Builder -----------------

def parse_price_to_float(price_str):
    """
    Extract the first numeric value from a price string (e.g., '£65 - £80').
    Returns 0.0 if none found or if the value is negative.
    """
    if not price_str:
        return 0.0
    s = str(price_str)
    m = re.search(r"\d+(?:\.\d+)?", s)
    if m:
        price = float(m.group(0))
        return price if price > 0 else 0.0
    return 0.0

def has_socks_keyword(product_data, fields=None):
    """
    Check if the keyword 'socks' is present in the product_data JSON.
    
    Args:
        product_data (dict): The JSON/dictionary containing product information.
        fields (list, optional): Specific fields in product_data to search in. 
                                If None, search all string values.
    
    Returns:
        bool: True if 'socks' is found, False otherwise.
    """
    if not product_data:
        return False
    
    keyword = 'socks'.lower()
    
    # If specific fields are provided, only search in those
    if fields:
        for field in fields:
            if field in product_data:
                value = str(product_data[field]).lower()
                if keyword in value:
                    return True
        return False
    
    # If no fields specified, search all string values in product_data
    def search_dict(data):
        for key, value in data.items():
            if isinstance(value, str):
                if keyword in value.lower():
                    return True
            elif isinstance(value, dict):
                if search_dict(value):
                    return True
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        if search_dict(item):
                            return True
                    elif isinstance(item, str):
                        if keyword in item.lower():
                            return True
        return False
    
    return search_dict(product_data)


def create_individual_sku(today_str, product_data):
    """Create individual SKU entries from product data for MongoDB insertion."""
    all_skus = []
    try:
        pid_raw = product_data.get("Product Id", "") or product_data.get("Product ID", "")
        # Set country-specific product_id prefix
        if country == "US":
            pid = f'skr{pid_raw}'
        elif country == "UK":
            pid = f'skr{pid_raw}'
        else:
            pid = f'skr{pid_raw}'
        # Color id variations
        color_id = product_data.get('Color Id', '') or product_data.get('Color ID', '')
        cid = product_data.get('Color Reference Code', color_id) or ''

        sku_base = product_data.get('SKU as per the website', pid)

        # Gender / age
        gender_std = remap_gender(product_data.get('Gender', ''))
        age_group = get_age_group(gender_std)
        age_range = get_age_range(gender_std)

        # Materials from Composition or Features
        composition = product_data.get('Features', [])
        materials = extract_materials(composition)

        # Occasion
        occasion_norm = remap_occasion(product_data.get('Occasion', ''))

        # Price parsing with positive value check
        price = parse_price_to_float(product_data.get('Price', ''))
        launch_price = parse_price_to_float(product_data.get('Launch Price', ''))

        # Demand
        demand = product_data.get('Demand', None)

        # Process images: replace 4th image with 'nffc' if it contains 'nffc'
        def get_images(images):
            """
            Process image URLs to assign image styles.
            - Default: all images = 's0'
            - Special rule: The first image is always assigned 'n_f_f_c'
            """
            image_list = []
            
            for idx, image in enumerate(images):
                if not image:
                    continue
                image_style = 's0'
                if idx == 0:  # First image always gets 'n_f_f_c'
                    image_style = 'n_f_f_c'
                image_list.append({
                    "url": image,
                    "image_style": image_style
                })

            return image_list

        # Sizes loop
        sizes = product_data.get('Sizes', []) or []
        for size in sizes:
            size_name = (size.get('Size name', '') or '').strip()
            size_ref = (size.get('Size Reference Code', '') or '').strip()

            # Availability
            availability_raw = size.get('Availability') or size.get('Availablity', '')  # Handle typo
            availability = 'in_stock' if str(availability_raw).strip().lower() == 'in stock' else 'out_of_stock'

            # Validate apparel size
            if not is_valid_apparel_size(size_name):
                print(f" Skipping non-valid apparel size: {size_name}")
                continue

            sku_value = f'{pid}%p{pid}c{cid}%s{size_ref}' if size_ref else f'{pid}%{sku_base}'
            cids=f'{pid}%{cid}'

            sku_entry = {
                'product_id': pid,
                'gender': gender_std,
                'age_group': age_group,
                'age_range': age_range,
                'date_of_scraping': parse_launch_date(today_str),
                'url': product_data.get('Product Url', ''),
                'title': product_data.get('Title', '').lower(),
                'description': product_data.get('Description', ''),
                'product_ref_code': product_data.get('Product Reference Code', pid_raw) or pid_raw,
                'color_id': cids,
                'color_name': product_data.get('Color Name', '').lower(),
                'color_ref_code': None,
                'sku': sku_value,
                'size_name': size_name,
                'size_ref_code': None,
                'price': price,
                'launch_price': launch_price,
                'availability': availability,
                'demand': demand,
                'composition': materials,
                'origin': None,
                'images': get_images(product_data.get('Images', []) or [])
                # 'brand': (product_data.get('Brand', 'Skechers') or 'Skechers').lower()
            }
            all_skus.append(sku_entry)

        return all_skus

    except Exception as e:
        print(f" Error creating SKU for {product_data.get('Product Url', 'unknown')}: {e}")
        traceback.print_exc()
        return []


# ----------------- JSON Ingestion -----------------

def process_jsons(today_str, country, collection):
    """
    Read product JSON files from:
        {country}/Data/{today_str}/Json_data/**.json
    and insert SKUs into MongoDB.
    """
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

                # Handle different JSON structures
                if isinstance(data, dict) and any(k in data for k in ('Product Id', 'Title', 'Product Url')):
                    products = [data]
                elif isinstance(data, list):
                    products = data
                elif isinstance(data, dict):
                    products = list(data.values())
                else:
                    print(f"Unrecognized JSON structure in {file_path}, skipping.")
                    continue
                
                for product in products:
                    if not isinstance(product, dict):
                        print(f"Invalid product data in {file_path}, skipping.")
                        continue
                
                if has_socks_keyword(product):
                        print(f" Skipping product in {file_path} due to 'socks' keyword")
                        continue
                for product in products:
                    skus = create_individual_sku(today_str, product)
                    if skus:
                        try:
                            collection.insert_many(skus, ordered=False)
                            for sku in skus:
                                print(f" Inserted SKU: Product_id: {sku['product_id']}, SKU: {sku['sku']}, Size: {sku['size_name']}")
                            total_products += 1
                        except BulkWriteError as bwe:
                            print(f"Bulk write error for {file_path}: {bwe.details}")
                    else:
                        print(f"No valid SKUs in {file_path}")

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

    # 🔧 Configure these:
    connection_string = "mongodb://localhost:27017"  # Your MongoDB URI
    db_name = "tg_analytics"            # Your DB name
    collection_name_prefix = "crawler_sink_skechers"

    today_str = date.today().strftime('%Y-%m-%d')   
    # today_str = '2025-12-03'

    countries_to_process = ["UK", "USA"]  # adjust as needed

    for country in countries_to_process:
        print(f"\nProcessing {country} ...")

        client, db, collection = connect_to_mongodb(connection_string, db_name, collection_name_prefix, country, today_str)
        if collection is None:
            print(f" Skipping {country} due to MongoDB connection failure")
            continue
        dates = os.listdir(f'{country}/Data')
        # for today_str in dates:
        process_jsons(today_str, country, collection)
        if client:
            client.close()
            print(f" Closed MongoDB connection for {country}")



# ----------------- Size Filter -----------------

def is_valid_apparel_size(size_name):
    """
    Validate apparel sizes: XS, S, M, L, XL, XXL, 3XL, 3XXL, and their variations (e.g., 'Large', 'X-Large', '3xl', '2xl').
    Exclude numeric sizes (e.g., '2', '3', '4', '2.0').
    """
    if size_name is None:
        return False
    
    # Convert to string, strip whitespace, and convert to lowercase for consistent comparison
    s = str(size_name).strip().lower()
    
    # Define valid apparel sizes (lowercase for matching)
    valid_sizes = [
        'xs', 's','m' , 'l', 'xl', 'xxl', '3xl', '3xxl',
        'x-small', 'small', 'medium', 'large', 'x-large', 'xx-large',
        'extra small', 'extra-small', 
        'extra large', 'extra-large',
        'double extra large', 'double-extra-large',
        'triple extra large', 'triple-extra-large'
    ]
    
    # Check if the size is purely numeric or a decimal (e.g., '2', '3', '2.0')
    if s.replace('.', '').isdigit():
        return False
    
    # Return True if the size is in valid_sizes
    return s in valid_sizes
# ----------------- SKU Builder -----------------

def parse_price_to_float(price_str):
    """
    Extract the first numeric value from a price string (e.g., '£65 - £80').
    Returns 0.0 if none found or if the value is negative.
    """
    if not price_str:
        return 0.0
    s = str(price_str)
    m = re.search(r"\d+(?:\.\d+)?", s)
    if m:
        price = float(m.group(0))
        return price if price > 0 else 0.0
    return 0.0

def has_socks_keyword(product_data, fields=None):
    """
    Check if the keyword 'socks' is present in the product_data JSON.
    
    Args:
        product_data (dict): The JSON/dictionary containing product information.
        fields (list, optional): Specific fields in product_data to search in. 
                                If None, search all string values.
    
    Returns:
        bool: True if 'socks' is found, False otherwise.
    """
    if not product_data:
        return False
    
    keyword = 'socks'.lower()
    
    # If specific fields are provided, only search in those
    if fields:
        for field in fields:
            if field in product_data:
                value = str(product_data[field]).lower()
                if keyword in value:
                    return True
        return False
    
    # If no fields specified, search all string values in product_data
    def search_dict(data):
        for key, value in data.items():
            if isinstance(value, str):
                if keyword in value.lower():
                    return True
            elif isinstance(value, dict):
                if search_dict(value):
                    return True
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        if search_dict(item):
                            return True
                    elif isinstance(item, str):
                        if keyword in item.lower():
                            return True
        return False
    
    return search_dict(product_data)


def create_individual_sku(today_str, product_data):
    """Create individual SKU entries from product data for MongoDB insertion."""
    all_skus = []
    try:
        pid_raw = product_data.get("Product Id", "") or product_data.get("Product ID", "")
        # Set country-specific product_id prefix
        if country == "US":
            pid = f'skr{pid_raw}'
        elif country == "UK":
            pid = f'skr{pid_raw}'
        else:
            pid = f'skr{pid_raw}'
        # Color id variations
        color_id = product_data.get('Color Id', '') or product_data.get('Color ID', '')
        cid = product_data.get('Color Reference Code', color_id) or ''

        sku_base = product_data.get('SKU as per the website', pid)

        # Gender / age
        gender_std = remap_gender(product_data.get('Gender', ''))
        age_group = get_age_group(gender_std)
        age_range = get_age_range(gender_std)

        # Materials from Composition or Features
        composition = product_data.get('Features', [])
        materials = extract_materials(composition)

        # Occasion
        occasion_norm = remap_occasion(product_data.get('Occasion', ''))

        # Price parsing with positive value check
        price = parse_price_to_float(product_data.get('Price', ''))
        launch_price = parse_price_to_float(product_data.get('Launch Price', ''))

        # Demand
        demand = product_data.get('Demand', None)

        # Process images: replace 4th image with 'nffc' if it contains 'nffc'
        def get_images(images):
            """
            Process image URLs to assign image styles.
            - Default: all images = 's0'
            - Special rule: The first image is always assigned 'n_f_f_c'
            """
            image_list = []
            
            for idx, image in enumerate(images):
                if not image:
                    continue
                image_style = 's0'
                if idx == 0:  # First image always gets 'n_f_f_c'
                    image_style = 'n_f_f_c'
                image_list.append({
                    "url": image,
                    "image_style": image_style
                })

            return image_list

        # Sizes loop
        sizes = product_data.get('Sizes', []) or []
        for size in sizes:
            size_name = (size.get('Size name', '') or '').strip()
            size_ref = (size.get('Size Reference Code', '') or '').strip()

            # Availability
            availability_raw = size.get('Availability') or size.get('Availablity', '')  # Handle typo
            availability = 'in_stock' if str(availability_raw).strip().lower() == 'in stock' else 'out_of_stock'

            # Validate apparel size
            if not is_valid_apparel_size(size_name):
                print(f" Skipping non-valid apparel size: {size_name}")
                continue

            sku_value = f'{pid}%p{pid}c{cid}%s{size_ref}' if size_ref else f'{pid}%{sku_base}'
            cids=f'{pid}%{cid}'

            sku_entry = {
                'product_id': pid,
                'gender': gender_std,
                'age_group': age_group,
                'age_range': age_range,
                'date_of_scraping': parse_launch_date(today_str),
                'url': product_data.get('Product Url', ''),
                'title': product_data.get('Title', '').lower(),
                'description': product_data.get('Description', ''),
                'product_ref_code': product_data.get('Product Reference Code', pid_raw) or pid_raw,
                'color_id': cids,
                'color_name': product_data.get('Color Name', '').lower(),
                'color_ref_code': None,
                'sku': sku_value,
                'size_name': size_name,
                'size_ref_code': None,
                'price': price,
                'launch_price': launch_price,
                'availability': availability,
                'demand': demand,
                'composition': materials,
                'made_in': None,
                'images': get_images(product_data.get('Images', []) or []),
                'brand': (product_data.get('Brand', 'Skechers') or 'Skechers').lower()
            }
            all_skus.append(sku_entry)

        return all_skus

    except Exception as e:
        print(f" Error creating SKU for {product_data.get('Product Url', 'unknown')}: {e}")
        traceback.print_exc()
        return []


# ----------------- JSON Ingestion -----------------

def process_jsons(today_str, country, collection):
    """
    Read product JSON files from:
        {country}/Data/{today_str}/Json_data/**.json
    and insert SKUs into MongoDB.
    """
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

                # Handle different JSON structures
                if isinstance(data, dict) and any(k in data for k in ('Product Id', 'Title', 'Product Url')):
                    products = [data]
                elif isinstance(data, list):
                    products = data
                elif isinstance(data, dict):
                    products = list(data.values())
                else:
                    print(f"Unrecognized JSON structure in {file_path}, skipping.")
                    continue
                
                for product in products:
                    if not isinstance(product, dict):
                        print(f"Invalid product data in {file_path}, skipping.")
                        continue
                
                if has_socks_keyword(product):
                        print(f" Skipping product in {file_path} due to 'socks' keyword")
                        continue
                for product in products:
                    skus = create_individual_sku(today_str, product)
                    if skus:
                        try:
                            collection.insert_many(skus, ordered=False)
                            for sku in skus:
                                print(f" Inserted SKU: Product_id: {sku['product_id']}, SKU: {sku['sku']}, Size: {sku['size_name']}")
                            total_products += 1
                        except BulkWriteError as bwe:
                            print(f"Bulk write error for {file_path}: {bwe.details}")
                    else:
                        print(f"No valid SKUs in {file_path}")

            except Exception as e:
                print(f" Error processing {file_path}: {e}")
                traceback.print_exc()

    return total_products


# ----------------- Main -----------------

if __name__ == "__main__":
    countries = {
        'UK': 'gb',
        'US': 'us'
    }

    # 🔧 Configure these:
    connection_string = "mongodb://localhost:27017"  # Your MongoDB URI
    db_name = "tg_analytics"            # Your DB name
    collection_name_prefix = "crawler_sink_skechers"

   
    today_str = date.today().strftime('%Y-%m-%d')   
    # today_str ='2025-11-28'

    countries_to_process = ["UK", "USA"]  # adjust as needed

    for country in countries_to_process:
        print(f"\nProcessing {country} ...")

        client, db, collection = connect_to_mongodb(connection_string, db_name, collection_name_prefix, country, today_str)
        if collection is None:
            print(f" Skipping {country} due to MongoDB connection failure")
            continue
        dates = os.listdir(f'{country}/Data')
        # for today_str in dates:
        process_jsons(today_str, country, collection)
        if client:
            client.close()
            print(f" Closed MongoDB connection for {country}")