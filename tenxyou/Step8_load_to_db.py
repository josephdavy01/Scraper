import os
import re
import json
import pymongo
import traceback
from datetime import datetime,date
from urllib.parse import urlparse


# ==================== UTILITIES ====================
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
            data = json.load(f)
            return {normalize_title(k): v for k, v in data.items()}
    except Exception as e:
        print(f"Failed to load product IDs: {e}")
        return {}


def load_color_ids(main_folder_path):
    color_file_path = os.path.join(main_folder_path, 'unique_colors_with_ids.json')
    try:
        with open(color_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {k.strip().lower(): v for k, v in data.items()}
    except Exception as e:
        print(f"Failed to load color IDs: {e}")
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
    text = " | ".join(str(f) for f in key_features).lower()
    match = re.search(r'weight[:\s]*(\d+(?:\.\d+)?)\s*g', text)
    return f"{match.group(1)}g" if match else None


def clean_product_name(product_name):
    if not product_name:
        return product_name
    name = product_name.strip()
    prefixes = ["men's ", "women's ", "mens ", "womens ", "Men's ", "Women's "]
    for prefix in prefixes:
        if name.lower().startswith(prefix.lower()):
            name = name[len(prefix):].strip()
    return name


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
    return ['kids'] if gender == 'kids' else ['adult']


def get_age_range(gender):
    return ['1y', '17y'] if gender == 'kids' else ['18y']


VALID_APPAREL_SIZES = {'xs', 's', 'm', 'l', 'xl', 'xxl', '2xl', '3xl', '4xl'}


def is_valid_apparel_size(size_str):
    return size_str.strip().lower() in VALID_APPAREL_SIZES


def sort_images_by_sequence(image_urls):
    def key_func(url):
        filename = os.path.basename(urlparse(url).path)
        match = re.match(r'^(\d+)', filename)
        return int(match.group(1)) if match else 999
    return sorted(image_urls, key=key_func)


def get_image_style_all_s0(image_urls):
    return [{"url": url, "image_style": "s0"} for url in image_urls]


# ==================== BULLETPROOF DESCRIPTION CLEANER ====================
def extract_clean_description(raw_description):
    """
    Extracts ONLY clean human-readable text from any rich/block/escaped JSON format.
    Handles: double-escaped strings, nested objects, blocks, data.text, etc.
    """
    if not raw_description:
        return ""

    texts = set()

    def dig_for_text(obj):
        if isinstance(obj, str):
            # Handle escaped JSON strings like "{\"heading\":\"\",\"data\":\"Real text\"}"
            cleaned = obj.strip()
            if cleaned.startswith(('{', '[', '"')):
                try:
                    parsed = json.loads(cleaned)
                    dig_for_text(parsed)
                    return
                except:
                    pass
            # Strip JSON noise and add meaningful fragments
            cleaned = re.sub(r'\\["\\]', '', cleaned)  # unescape
            cleaned = re.sub(r'["\'{}\[\]]', ' ', cleaned)
            cleaned = re.sub(r'\s+(heading|type|data|id|version|time|TEXT)\s*[:=]\s*["\']?[^"\']*["\']?', ' ', cleaned, flags=re.I)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned and len(cleaned) > 8:
                texts.add(cleaned)

        elif isinstance(obj, dict):
            for v in obj.values():
                dig_for_text(v)
            # Special handling for common keys
            if 'text' in obj:
                dig_for_text(obj['text'])
            if 'data' in obj:
                dig_for_text(obj['data'])
            if 'TEXT' in obj:
                dig_for_text(obj['TEXT'])

        elif isinstance(obj, list):
            for item in obj:
                dig_for_text(item)

    # Start digging
    try:
        if isinstance(raw_description, str) and raw_description.strip().startswith(('{', '[')):
            parsed = json.loads(raw_description)
            dig_for_text(parsed)
        else:
            dig_for_text(raw_description)
    except:
        dig_for_text(raw_description)  # fallback

    # Final assembly
    result = " | ".join(sorted(texts, key=len, reverse=True))
    result = re.sub(r'\s+', ' ', result).strip()
    result = re.sub(r'^\|+| \|+$', '', result).strip()
    return result if result else "No description available"


# ==================== COMPOSITION EXTRACTOR ====================
def extract_composition_all_sources(product, desc_blocks, key_features, metadata):
    composition_lines = set()
    pattern = re.compile(r'\d+%?.*?(cotton|polyester|viscose|wool|linen|silk|nylon|spandex|elastane|leather|mesh|polyamide|acrylic|lycra)', re.IGNORECASE)

    sources = [product.get('description', '')]
    sources.extend(key_features or [])
    sources.extend(desc_blocks or [])

    if 'productDetails' in metadata:
        try:
            details = json.loads(metadata['productDetails'])
            for item in details:
                txt = item.get('TEXT') or item.get('text')
                if isinstance(txt, (str, list)):
                    sources.extend(txt if isinstance(txt, list) else [txt])
        except:
            pass

    for text in sources:
        if not text:
            continue
        for line in str(text).split('\n'):
            line = line.strip()
            if not line or len(line) < 10:
                continue
            cleaned = re.sub(r'^[•\-\*\>\[\]\(\)\s]+', '', line).strip()
            if re.search(r'\d+\s*%?', cleaned) and pattern.search(cleaned):
                cleaned = re.sub(r'\s*\(inclusive of all taxes\).*', '', cleaned, flags=re.I)
                cleaned = re.sub(r'\s*GST.*', '', cleaned, flags=re.I)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
                if not any(bad in cleaned.lower() for bad in ['100% genuine', 'tax', 'price']):
                    composition_lines.add(cleaned.capitalize())

    if composition_lines:
        return " | ".join(sorted(composition_lines, key=len))
    return None


# ==================== MAIN JSON PROCESSOR ====================
def create_individual_json(today_str, json_data, file_gender, product_ids, color_ids):
    all_products = []

    if not json_data or not isinstance(json_data, dict):
        return []

    try:
        node = json_data['api_data']['data']['productVariants']['edges'][0]['node']
        product = node['product']

        orig_title = product['name']
        normalized_title = normalize_title(orig_title)
        product_id = product_ids.get(normalized_title, 'null')
        clean_title = clean_product_name(orig_title).lower()

        url = json_data['url']
        collections = [c['slug'] for c in product['collections']]

        if 'unisex' in collections:
            gender = 'male'
        elif 'women' in collections:
            gender = 'female'
        elif any(x in collections for x in ['men', 'mens']):
            gender = 'male'
        elif 'kids' in collections:
            gender = 'kids'
        else:
            gender = file_gender or 'male'

        raw_description = product.get('description', '')
        metadata = {m['key']: m['value'] for m in product.get('metadata', [])}
        launch_price = float(metadata.get('MRP_MONEY', '0') or 0.0)
        origin = extract_origin(metadata)

        # Extract key features
        key_features = []
        if 'productDetails' in metadata:
            try:
                details = json.loads(metadata['productDetails'])
                for d in details:
                    txt = d.get('TEXT') or d.get('text')
                    if isinstance(txt, list):
                        key_features.extend([t.strip() for t in txt if t.strip()])
                    elif txt:
                        key_features.append(txt.strip())
            except:
                pass

        # Extract description blocks for composition
        desc_blocks = []
        try:
            if isinstance(raw_description, str) and raw_description.strip().startswith('{'):
                desc_json = json.loads(raw_description)
                if 'blocks' in desc_json:
                    for block in desc_json['blocks']:
                        inner_text = block.get('data', {}).get('text') or block.get('text', '')
                        if isinstance(inner_text, str) and inner_text.strip().startswith('{'):
                            try:
                                inner_text = json.loads(inner_text)
                            except:
                                pass
                        desc_blocks.append(inner_text)
        except:
            pass

        # FINAL CLEAN DESCRIPTION
        full_description = extract_clean_description(raw_description)
        if key_features:
            full_description += " | " + " | ".join(key_features)

        composition = extract_composition_all_sources(product, desc_blocks, key_features, metadata)
        available_sizes = [s.lower() for s in json_data.get('available_size', [])]

        for variant in product.get('variants', []):
            size_info = next(
                (a['values'][0] for a in variant.get('attributes', [])
                 if a['attribute']['name'] == 'Size'), None)
            color_info = next(
                (a['values'][0] for a in variant.get('attributes', [])
                 if a['attribute']['name'] == 'Color'), None)

            if not size_info or not color_info:
                continue

            size_name = size_info['name'].strip()
            if not is_valid_apparel_size(size_name):
                continue

            color_name = color_info['name'].strip().lower()
            color_ref_code = color_ids.get(color_name, 'null')

            price = variant['pricing']['price']['gross']['amount']
            raw_images = [m['url'] for m in variant.get('media', []) if m['type'] == 'IMAGE']
            images = get_image_style_all_s0(sort_images_by_sequence(raw_images))

            in_stock = size_name.lower() in available_sizes
            availability = 'out_of_stock' if in_stock else 'in_stock'

            entry = {
                "product_id": f"ten{product_id}",
                "gender": gender,
                "age_group": get_age_group(gender),
                "age_range": get_age_range(gender),
                "date_of_scraping": parse_launch_date(today_str),
                "url": url,
                "title": clean_title,
                "description": full_description.strip(),
                "product_ref_code": product['id'],
                "color_id": f"ten{product_id}%{color_ref_code}",
                "color_name": color_name,
                "color_ref_code": color_ref_code,
                "sku": f"ten{product_id}%p{product_id}c{color_ref_code}s{size_name.upper()}",
                "size_name": size_name.upper(),
                "size_ref_code": size_info.get('reference_code'),
                "price": price,
                "launch_price": launch_price,
                "availability": availability,
                "composition": composition or "null",
                "origin": origin,
                "occasion": None,
                "images": images
            }
            all_products.append(entry)

    except Exception as e:
        print(f"Error processing product: {e}")
        traceback.print_exc()

    return all_products


# ==================== MAIN PROCESSOR ====================
def process_jsons(today_str, collection):
    main_folder = os.getcwd()
    product_ids = load_product_ids(main_folder)
    color_ids = load_color_ids(main_folder)

    print(f"Loaded {len(product_ids)} product titles & {len(color_ids)} colors")

    for root, _, files in os.walk(main_folder):
        for file in files:
            if not file.endswith('.json') or file in ['unique_titles_with_ids.json', 'unique_colors_with_ids.json']:
                continue

            file_path = os.path.join(root, file)
            gender_guess = os.path.basename(root).lower()

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                products = create_individual_json(today_str, data, gender_guess, product_ids, color_ids)

                if products:
                    for p in products:
                        collection.insert_one(p)
                    print(f"INSERTED {len(products)} variants ← {os.path.basename(file)} | {p['title'][:60]}...")
                else:
                    print(f"Skipped {file} → No valid XS–4XL sizes")

            except Exception as e:
                print(f"FAILED {file_path}: {e}")
                traceback.print_exc()


if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-09'


    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client['tg_analytics_tenxyou']
    collection = db['crawler_sink_tenxyou_india_apparel']

    try:
        collection.drop_index("sku_1")
        print("Dropped old SKU index")
    except:
        pass

    print("Starting Tenxyou India Apparel Processing (XS to 4XL only)...")
    process_jsons(today_str, collection)
    print("APPAREL DATA LOAD COMPLETED SUCCESSFULLY!")
    client.close()