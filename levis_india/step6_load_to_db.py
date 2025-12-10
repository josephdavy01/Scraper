import os
import re
import json
from datetime import datetime
import traceback
import pymongo
from pymongo.errors import BulkWriteError
from collections import Counter
from bs4 import BeautifulSoup


def parse_launch_date(date_string):
    """Parse various date formats into a datetime object."""
    format_strings = [
        '%Y-%m-%dT%H:%M:%S.%f%z',  # With milliseconds and timezone
        '%Y-%m-%dT%H:%M:%S%z',     # Without milliseconds, with timezone
        '%Y-%m-%d',                # Date only
        '%Y-%m-%d %H:%M:%S.%f'     # With milliseconds, no timezone
    ]
    for fmt in format_strings:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_string}")


def clean_description(html_description):
    """Remove HTML tags from description and preserve plain text with newlines."""
    if not html_description:
        return ''
    soup = BeautifulSoup(html_description, 'html.parser')
    text = '\n'.join(line.strip() for line in soup.get_text(separator='\n').splitlines() if line.strip())
    return text


def connect_to_mongodb(connection_string, db_name, collection_name_prefix, country):
    """Connect to MongoDB and return the collection for the specified country."""
    try:
        client = pymongo.MongoClient(connection_string)
        db = client[db_name]
        collection = db[f'{collection_name_prefix}_{country.lower()}']
        print(f"Connected to MongoDB collection: {collection.name}")
        return client, db, collection
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        traceback.print_exc()
        return None, None, None


def remap_gender(handle):
    """Determine gender based on the handle field with debug logging."""
    if not handle:
        print("Debug: Handle is empty or None, returning 'unisex'")
        return 'unisex'
    handle_lower = handle.lower()
    print(f"Debug: Processing handle: {handle_lower}")
    if 'womens' in handle_lower or 'women' in handle_lower:
        print(f"Debug: Found 'women' or 'womens' in handle, gender set to 'female'")
        return 'female'
    if 'mens' in handle_lower or 'men' in handle_lower:
        print(f"Debug: Found 'men' or 'mens' in handle, gender set to 'male'")
        return 'male'
    if 'kids' in handle_lower:
        print(f"Debug: Found 'kids' in handle, gender set to 'kids'")
        return 'kids'
    print(f"Debug: No gender keywords found in handle, defaulting to 'unisex'")
    return 'unisex'


def get_age_group(gender_std):
    """Determine age group based on gender."""
    return ['kids'] if gender_std == 'kids' else ['adult']


def get_age_range(gender_std):
    """Determine age range based on gender."""
    return ['0y', '17y'] if gender_std == 'kids' else ['18y']


def remap_occasion(description, tags):
    """Normalize occasion field based on description and tags."""
    description = description.lower() if description else ''
    tags = [tag.lower() for tag in tags] if tags else []
    if 'casual' in description or 'casual' in tags:
        return 'casual'
    if 'formal' in description or 'formal' in tags:
        return 'formal'
    if 'athletic' in description or 'sport' in tags:
        return 'athletic'
    return 'casual'


def extract_materials(composition):
    """Extract material-related details containing percentages from composition_and_care."""
    if not isinstance(composition, list) or not composition:
        return 'None'
    cleaned_items = []
    for item in composition:
        if '%' in item:
            cleaned_item = item.strip()
            cleaned_items.append(cleaned_item)
    return ', '.join(cleaned_items) if cleaned_items else 'None'


def is_valid_apparel_size(size_name):
    """Validate apparel sizes, accepting single numerical sizes (e.g., '32') and standard sizes (e.g., 'S', 'M', 'XL')."""
    if size_name is None:
        return False
    size_name = str(size_name).strip().upper()
    return bool(re.match(r'^\d+$|^\d+\s*/\s*\d+$|^(XXS|XS|S|M|L|XL|XXL|XXXL|XXXXL)$', size_name))


def parse_price_to_float(price):
    """Convert price (e.g., 164900) to float (e.g., 1649.00)."""
    try:
        return float(price) / 100 if price else 0.0
    except (ValueError, TypeError):
        return 0.0


def has_socks_keyword(product_data, fields=None):
    """Check if 'socks' is present in product_data."""
    if not product_data:
        return False
    keyword = 'socks'.lower()
    
    if fields:
        for field in fields:
            if field in product_data:
                value = str(product_data[field]).lower()
                if keyword in value:
                    return True
        return False
    
    def search_dict(data):
        for key, value in data.items():
            if isinstance(value, str) and keyword in value.lower():
                return True
            elif isinstance(value, dict):
                if search_dict(value):
                    return True
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and search_dict(item):
                        return True
                    elif isinstance(item, str) and keyword in item.lower():
                        return True
        return False
    return search_dict(product_data)


def load_pid_mapping(pid_file_path):
    """Load the PID mapping from levis_pid_remapping.json."""
    try:
        if os.path.exists(pid_file_path):
            with open(pid_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"PID mapping file not found at {pid_file_path}")
            return {}
    except Exception as e:
        print(f"Error loading PID mapping from {pid_file_path}: {e}")
        return {}


def get_mapped_pid(pdict, handle, variant_ids):
    """Get the mapped PID from pdict based on handle or variant IDs."""
    if not pdict:
        return None
    handle = str(handle).strip() if handle else ''
    variant_ids = [str(vid) for vid in variant_ids] if variant_ids else []
    
    for pid, identifiers in pdict.items():
        if handle and handle in identifiers:
            print(f"Debug: Found PID {pid} for handle: {handle}")
            return f"lev{pid}"
        for vid in variant_ids:
            if vid in identifiers:
                print(f"Debug: Found PID {pid} for variant_id: {vid}")
                return f"lev{pid}"
    print(f"Debug: No PID mapping found for handle: {handle}, variant_ids: {variant_ids}")
    return None


def create_individual_sku(today_str, product_data, country, option2_counts, pdict):
    """Create individual SKU entries from product data for MongoDB insertion and count option2 values."""
    all_skus = []
    try:
        hulkapps_data = product_data.get("hulkapps_product_json", {})
        if not hulkapps_data:
            print("No hulkapps_product_json found, skipping.")
            return []

        # PID generation using pdict
        handle = hulkapps_data.get('handle', '')
        variant_ids = [str(v.get('id', '')) for v in hulkapps_data.get('variants', [])]
        pid = get_mapped_pid(pdict, handle, variant_ids)
        if not pid:
            raw_id = str(hulkapps_data.get("id", ""))
            pid = f"lev{raw_id}"  # Fallback to lev + raw_id
            print(f"No PID mapping found for handle: {handle}, variant_ids: {variant_ids}, using default pid: {pid}")
        
        # Derive pid_raw by removing "lev" prefix from pid
        pid_raw = pid[3:] if pid.startswith("lev") else pid
        pid_ref = str(hulkapps_data.get("id", ""))

        gender_std = remap_gender(handle)
        age_group = get_age_group(gender_std)
        age_range = get_age_range(gender_std)
        materials = extract_materials(product_data.get('composition_and_care', []))
        raw_description = hulkapps_data.get('description', '')
        cleaned_description = clean_description(raw_description)
        occasion_norm = remap_occasion(cleaned_description, hulkapps_data.get('tags', []))

        price = parse_price_to_float(hulkapps_data.get('price', 0))
        launch_price = parse_price_to_float(hulkapps_data.get('compare_at_price', 0))

        def get_images(images):
            """Process image URLs, ensuring they start with https."""
            image_list = []
            for idx, image in enumerate(images):
                if not image:
                    continue
                if image.startswith('https://'):
                    url = image
                elif image.startswith('//'):
                    url = f'https:{image}'
                elif image.startswith('http://'):
                    url = f'https://{image[7:]}'
                else:
                    url = f'https://{image}'
                print(f"Debug: Processed image URL: {url}")
                image_style = 'n_f_f_c' if idx == 0 else 's0'
                image_list.append({
                    "url": url,
                    "image_style": image_style
                })
            return image_list

        images = get_images(hulkapps_data.get('images', []))

        # Extract color_id from handle
        color_id = handle.rsplit('-', 1)[-1] if handle and '-' in handle else None
        print(f"Debug: Extracted color_id from handle {handle}: {color_id}")

        variants = hulkapps_data.get('variants', [])
        for variant in variants:
            size_name = variant.get('option2', '')
            if not size_name or not is_valid_apparel_size(size_name):
                size_name = variant.get('option1', '') or variant.get('title', '')
            
            size_ref = str(variant.get('id', ''))  # Use variant id as size_ref_code
            cids = f'{pid}%{color_id if color_id else "None"}'  # Use pid with "lev"
            availability = 'in_stock' if variant.get('available', False) else 'out_of_stock'

            option2_value = variant.get('option2', '')
            if option2_value:
                option2_counts[option2_value] += 1

            if not is_valid_apparel_size(size_name):
                print(f"Skipping non-valid apparel size: {size_name}")
                continue

            sku_value = f'{pid}%p{pid_raw}c{color_id if color_id else "None"}%s{size_ref}' if size_ref else f'{pid}%p{pid_raw}'
            
            sku_entry = {
                'product_id': pid,  # Use pid (with "lev" prefix from mapping or fallback)
                'gender': gender_std,
                'age_group': age_group,
                'age_range': age_range,
                'date_of_scraping': parse_launch_date(today_str),
                'url': f"https://levi.in/products/{hulkapps_data.get('handle', '')}",
                'title': hulkapps_data.get('title', '').lower(),
                'description': cleaned_description,
                'product_ref_code': pid_ref ,  # Raw ID without "lev"
                'color_id': cids,
                'color_name': variant.get('option1', '').lower(),
                'color_ref_code': None,
                'sku': sku_value,  # Uses pid_raw without "lev"
                'size_name': size_name,
                'size_ref_code': size_ref,
                'price': price,
                'launch_price': launch_price,
                'availability': availability,
                'demand': None,
                'composition': materials,
                'origin': None,
                'images': images,
            }
            all_skus.append(sku_entry)

        return all_skus

    except Exception as e:
        print(f"Error creating SKU for {hulkapps_data.get('handle', 'unknown')}: {e}")
        traceback.print_exc()
        return []


def process_json_files(today_str, country, collection, pid_file_path):
    """Process JSON files in {country}/data/{today_str}/Json_data/** and count option2 values."""
    total_products = 0
    option2_counts = Counter()
    json_output_folder = os.path.join(country, 'data', today_str, 'Json_data')
    
    # Load PID mapping
    pdict = load_pid_mapping(pid_file_path)

    if not os.path.exists(json_output_folder):
        print(f"Folder not found: {json_output_folder}")
        return 0, option2_counts

    json_files = []
    for root, _, files in os.walk(json_output_folder):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))

    if not json_files:
        print(f"No JSON files found in {json_output_folder}/**")
        return 0, option2_counts

    print(f"Found {len(json_files)} JSON files in {json_output_folder}/**")

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as jf:
                json_data = json.load(jf)

            if has_socks_keyword(json_data, fields=['title', 'description', 'tags']):
                print(f"Skipping product in {file_path} due to 'socks' keyword")
                continue

            skus = create_individual_sku(today_str, json_data, country, option2_counts, pdict)
            if not skus:
                print(f"No valid SKUs in {file_path}")
                continue

            try:
                collection.insert_many(skus, ordered=False)
                for sku in skus:
                    print(f"Inserted SKU: Product_id: {sku['product_id']}, SKU: {sku['sku']}, Size: {sku['size_name']}, Gender: {sku['gender']}, Size_ref_code: {sku['size_ref_code']}, Color_id: {sku['color_id']}")
                total_products += 1
            except BulkWriteError as bwe:
                print(f"Bulk write error for {file_path}: {bwe.details}")

        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {file_path}: {e}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            traceback.print_exc()

    print("\nOption2 value counts across all variants:")
    for value, count in option2_counts.items():
        print(f"{value}: {count}")

    return total_products, option2_counts


if __name__ == "__main__":
    country = "levis_India"  # Updated to match log
    connection_string = "mongodb://localhost:27017"  # Your MongoDB URI
    db_name = 'tg_analytics'           # Your DB name
    collection_name_prefix = f'crawler_sink'
    today_str = datetime.now().strftime('%Y-%m-%d')  # Today's date (2025-10-09)
    pid_file_path = 'levis_pid_remapping.json'  # Path to PID mapping file

    client, db, collection = connect_to_mongodb(connection_string, db_name, collection_name_prefix, country)
    if collection is None:
        print("MongoDB connection failed, exiting.")
        exit(1)

    print(f"\nProcessing {country} for date {today_str}...")
    data_dir = os.path.join(country, "data")
    # dates = os.listdir(data_dir)
    # for today_str in dates:
    total_products, option2_counts = process_json_files(today_str, country, collection, pid_file_path)

    print(f"Processed {total_products} products for {country}")

    if client:
        client.close()
        print(f"Closed MongoDB connection for {country}")