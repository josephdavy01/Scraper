import os
import re
import json
import pymongo
import traceback
from datetime import datetime,date
from urllib.parse import urlparse

# -------------------- Utility Functions -------------------- #

def normalize_title(title):
    prefixes_to_remove = ["men's ", "women's ", "mens ", "womens "]
    title = title.lower().strip()
    for prefix in prefixes_to_remove:
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
    return title

def load_product_ids(main_folder_path):
    ids_file_path = os.path.join(main_folder_path, 'unique_titles_with_ids.json')
    try:
        with open(ids_file_path, 'r', encoding='utf-8') as f:
            product_ids_raw = json.load(f)
        return {normalize_title(k): v for k, v in product_ids_raw.items()}
    except Exception as e:
        print(f"Failed to load product IDs from {ids_file_path}: {e}")
        return {}

def load_color_ids(main_folder_path):
    color_file_path = os.path.join(main_folder_path, 'unique_colors_with_ids.json')
    try:
        with open(color_file_path, 'r', encoding='utf-8') as f:
            color_ids_raw = json.load(f)
        return {k.lower(): v for k, v in color_ids_raw.items()}
    except Exception as e:
        print(f"Failed to load color IDs from {color_file_path}: {e}")
        return {}

def parse_launch_date(date_string):
    formats = ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S.%f']
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    raise ValueError(f"Date parsing failed: {date_string}")

def extract_weight_from_features(key_features):
    if not key_features:
        return None
    for feature in key_features:
        match = re.search(r'weight[:\s]*(\d+(?:\.\d+)?)\s*g', feature.lower())
        if match:
            return f"{match.group(1)}g"
    return None

def clean_product_name(product_name):
    if not product_name:
        return product_name
    name = product_name.strip()
    prefixes = ["men's ", "women's ", "mens ", "womens ", "Women's", "Men's"]
    for prefix in prefixes:
        if name.lower().startswith(prefix.lower()):
            return name[len(prefix):].strip()
    return name

def is_footwear(json_data):
    try:
        product = json_data['api_data']['data']['productVariants']['edges'][0]['node']['product']
        category = product['category']['name'].lower()
        return any(keyword in category for keyword in ['shoe', 'sneaker', 'lace up'])
    except:
        return False

def extract_origin(metadata):
    if 'MORE_ABOUT_ORIGIN' in metadata:
        try:
            origin_data = json.loads(metadata['MORE_ABOUT_ORIGIN'])
            for item in origin_data[0]['data']:
                if 'Country of Origin' in item['text']:
                    return item['text'].split(':')[-1].strip().lower()
        except:
            pass
    return 'india'

def get_age_group(gender):
    if gender in ['female', 'male']:
        return ['adult']
    if gender == 'kids':
        return ['kids']
    return ['adult']

def get_age_range(gender):
    if gender in ['female', 'male']:
        return ['18y']
    if gender == 'kids':
        return ['1y', '17y']
    return ['18y']

def clean_size_name(size_name):
    if not size_name:
        return ""
    for pattern in ['Only', 'No items', 'Notify me']:
        size_name = size_name.split(pattern)[0]
    return size_name.strip()

# ---------- NEW IMAGE FUNCTIONS ---------- #

def sort_images_by_sequence(image_urls):
    def key_func(url):
        filename = os.path.basename(urlparse(url).path)
        match = re.match(r'^(\d+)', filename)
        return int(match.group(1)) if match else 999
    return sorted(image_urls, key=key_func)

def get_image_style_all_s0(image_urls):
    return [{"url": url, "image_style": "s0"} for url in image_urls]

# -------------------- Extraction Functions -------------------- #

def extract_detail_from_description(desc_blocks, keyword_patterns):
    if not desc_blocks:
        return None
    for block in desc_blocks:
        text = ""
        if isinstance(block, dict):
            data = block.get('data', '')
            if isinstance(data, str):
                text = data
            elif isinstance(data, list):
                text = " ".join(str(d) for d in data)
        elif isinstance(block, str):
            text = block
        text_lower = text.lower()
        for pattern in keyword_patterns:
            if re.search(pattern, text_lower):
                return text.strip()
    return None

def extract_heel_to_toe_drop(desc_blocks):
    return extract_detail_from_description(desc_blocks, [r'heel[-\s]*to[-\s]*toe drop', r'heel drop'])

def extract_sole_material(desc_blocks):
    return extract_detail_from_description(desc_blocks, [r'sole material', r'outsole', r'sole'])

def extract_closure_type(desc_blocks):
    return extract_detail_from_description(desc_blocks, [r'closure type', r'lacing', r'lace up', r'slip on'])

# -------------------- JSON Processing -------------------- #

def create_individual_json(today_str, json_data, file_gender, product_ids, color_ids):
    all_products = []
    if not json_data or not isinstance(json_data, dict):
        print(f"Skipping: Invalid or empty JSON data")
        return []

    if not is_footwear(json_data):
        return []

    try:
        node = json_data['api_data']['data']['productVariants']['edges'][0]['node']
        product = node['product']
        orig_title = product['name']
        normalized_title = normalize_title(orig_title)
        product_id = product_ids.get(normalized_title, 'null')
        name = clean_product_name(orig_title).lower()
        url = json_data['url']
        collections = [c['slug'] for c in product['collections']]

        if 'unisex' in collections:
            gender = 'male'
        elif 'women' in collections:
            gender = 'female'
        elif 'men' in collections or 'mens' in collections:
            gender = 'male'
        elif 'kids' in collections:
            gender = 'kids'
        else:
            gender = file_gender or 'unisex'

        description = product.get('description', '')
        desc_blocks = []
        try:
            desc_json = json.loads(description)
            inner_text = json.loads(desc_json['blocks'][0]['data']['text'])
            desc_blocks = inner_text if isinstance(inner_text, list) else []
            description = " ".join(
                block.get('data', '') if isinstance(block, dict) else str(block)
                for block in desc_blocks
            )
        except Exception:
            pass

        metadata = {m['key']: m['value'] for m in product.get('metadata', [])}
        launch_price = float(metadata.get('MRP_MONEY', '0'))
        origin = extract_origin(metadata)

        key_features = []
        if 'productDetails' in metadata:
            try:
                details = json.loads(metadata['productDetails'])
                for d in details:
                    if isinstance(d['TEXT'], list):
                        key_features.extend(d['TEXT'])
                    elif isinstance(d['TEXT'], str):
                        key_features.append(d['TEXT'])
            except Exception:
                pass
        if key_features:
            description += '\n' + ' | '.join(key_features)

        heel_to_toe_drop = extract_heel_to_toe_drop(desc_blocks)
        sole_material = extract_sole_material(desc_blocks)
        closure_type = extract_closure_type(desc_blocks)

        available_sizes = json_data.get('available_size', [])
        normalized_available_sizes = [s.lower() for s in available_sizes]

        for variant in product.get('variants', []):
            if not variant:
                continue
            size_info = next((attr['values'][0] for attr in variant['attributes'] if attr['attribute']['name'] == 'Size'), None)
            color_info = next((attr['values'][0] for attr in variant['attributes'] if attr['attribute']['name'] == 'Color'), None)
            if not size_info or not color_info:
                continue
            size_name = f"{size_info['name']}"
            size_key_name = size_info['name'].lower()
            size_availability = size_key_name in normalized_available_sizes
            size_cleaned = clean_size_name(size_info['name'])
            if not size_cleaned:
                continue

            color_name = color_info['name'].strip().lower()
            color_ref_code = color_ids.get(color_name, 'null')

            size_specific_sku = variant.get('sku', '')
            availability = 'out_of_stock' if size_availability else 'in_stock'
            variant_price = variant['pricing']['price']['gross']['amount']
            # IMAGE LOGIC HERE
            raw_images = [m['url'] for m in variant.get('media', []) if m['type'] == 'IMAGE']
            sorted_images = sort_images_by_sequence(raw_images)
            images = get_image_style_all_s0(sorted_images)

            entry = {
                "product_id": f'ten{product_id}',
                "gender": gender,
                "age_group": get_age_group(gender),
                "age_range": get_age_range(gender),
                "date_of_scraping": parse_launch_date(today_str),  # datetime object!
                "url": url,
                "title": name,
                "description": description,
                "product_ref_code": product['id'],
                "color_id": 'ten'+f'{product_id}%{color_ref_code}',
                "color_name": color_name,
                "color_ref_code": color_ref_code,
                "sku": 'ten'+f'{product_id}%p{product_id}c{color_ref_code}s{size_name}',
                "size_name": size_name,
                "size_ref_code": size_info.get('reference_code'),
                "price": variant_price,
                "launch_price": launch_price,
                "availability": availability,
                "sole_material": sole_material,
                "upper_material": None,
                "closure_type": closure_type,
                "toe_shape": None,
                "heel_type": None,
                "weight": extract_weight_from_features(key_features),
                "heel_to_toe_drop": heel_to_toe_drop,
                "occasion": None,
                "origin": origin,
                "images": images
            }
            all_products.append(entry)
    except Exception as e:
        print(f"Error processing JSON data: {e}")
        traceback.print_exc()
        return []

    return all_products

# -------------------- Main Processing -------------------- #

def process_jsons(today_str, collection):
    main_folder = os.getcwd()
    product_ids = load_product_ids(main_folder)
    color_ids = load_color_ids(main_folder)

    for root, dirs, files in os.walk(main_folder):
        for file in files:
            if not file.endswith('.json'):
                continue
            if file in ['unique_titles_with_ids.json', 'unique_colors_with_ids.json']:
                continue
            file_path = os.path.join(root, file)
            gender_guess = os.path.basename(root).lower()
            try:
                with open(file_path, 'r', encoding='utf-8') as json_file:
                    data = json.load(json_file)
                skus = create_individual_json(today_str, data, gender_guess, product_ids, color_ids)
                if skus:
                    for sku in skus:
                        # datetime is allowed, no conversion to string!
                        collection.insert_one(sku)
                        print(f'Inserted Product_id: {sku["product_id"]}, SKU: {sku["sku"]}')
                else:
                    print(f"Skipping {file_path} - not footwear or missing data")
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                traceback.print_exc()

# -------------------- Entry Point -------------------- #

if __name__ == "__main__":
    today = date.today()
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-09'
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics_tenxyou']
    countries = ['India']
    for country in countries:
        collection = db[f'crawler_sink_tenxyou_{country.lower()}_footwear']

        # Drop unique index on SKU if exists
        try:
            collection.drop_index("sku_1")
            print("Dropped unique index on 'sku'. Duplicates allowed now.")
        except Exception:
            pass  # index might not exist, ignore

        print(f"Processing {country} footwear...")
        process_jsons(today_str, collection)
        print(f"Footwear data loading for {country} completed!")
    client.close()
