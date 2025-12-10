#!/usr/bin/env python3
import os
import re
import json
import pymongo
import traceback
from datetime import datetime

# ==================== PATHS ====================
BASE_PROJECT_DIR = "new_balance_products"
JSON_DATA_DIR = os.path.join("US", "data", "2025-11-06", "json_data", BASE_PROJECT_DIR)
TODAY_STR = "2025-11-05"
COUNTRY = "US"
# ==============================================


def parse_launch_date(date_string):
    return datetime.strptime(TODAY_STR, '%Y-%m-%d')


def extract_materials(text):
    text = text.lower()
    upper = "synthetic"
    sole = "rubber"
    closure = "lace-up"
    drop = None

    if any(x in text for x in ["mesh", "knit", "engineered mesh"]):
        upper = "mesh"
    elif "leather" in text:
        upper = "leather"
    elif "suede" in text:
        upper = "suede"

    if "eva" in text or "fresh foam" in text:
        sole = "eva"
    elif "fuelcell" in text:
        sole = "fuelcell"

    if "zip" in text or "boa" in text:
        closure = "zip" if "zip" in text else "boa"

    drop_match = re.search(r'(\d+(?:\.\d+)?)\s*mm\s*drop', text)
    if drop_match:
        drop = drop_match.group(1) + "mm"

    return upper, sole, closure, drop


def extract_weight(text):
    if not text:
        return None
    match = re.search(r'(\d+(?:\.\d+)?)\s*(grams|g|oz)', text, re.I)
    if match:
        val = float(match.group(1))
        unit = match.group(2).lower()
        if 'oz' in unit:
            val = round(val * 28.35, 1)
        return f"{val}g"
    return None


def get_gender_from_sku(sku):
    sku_upper = sku.upper()
    if '-W-' in sku_upper or sku_upper.endswith('W'):
        return 'female'
    if '-M-' in sku_upper or sku_upper.endswith('M'):
        return 'male'
    if any(w in sku_upper for w in ['2A', 'B', 'N']):
        return 'female'
    if any(w in sku_upper for w in ['D', '2E', '4E', 'EE']):
        return 'male'
    return 'unisex'


def get_image_style(image_urls):
    if not image_urls:
        return []
    if isinstance(image_urls, str):
        image_urls = [image_urls]
    result = []
    for item in image_urls:
        url = item.get('url') if isinstance(item, dict) else item
        if not url:
            continue
        base = url.split('?')[0]
        result.extend([
            {"url": base + "?$dw_detail_gallery$", "image_style": "s0"},
            {"url": base + "?$dw_detail_gallery$", "image_style": "n_f_f_c"}
        ])
    return result


def extract_cid_from_image(image_url):
    if not image_url:
        return ''
    filename = image_url.split('/')[-1].split('?')[0]
    name = os.path.splitext(filename)[0]
    parts = name.split('_')[0].split('-')
    return parts[-1].lower() if len(parts) > 1 else name.lower()[:8]


def get_age_group(gender):
    return ["kids"] if gender == "kids" else ["adult"]


def get_age_range(gender):
    return ["1y", "17y"] if gender == "kids" else ["18y"]


def create_individual_json(today_str, json_data, file_gender='unisex'):
    all_products = []
    seen_combinations = set()

    if not json_data or not isinstance(json_data, dict):
        return []

    ld = json_data.get('ld_json', {})
    details = json_data.get('details', {})
    url = json_data.get('url', '')
    product_id_from_file = json_data.get('product_id', '')

    model_name = ld.get('name', 'unknown').strip()
    clean_name = re.sub(r"[^a-zA-Z0-9\s]", "", model_name).lower()
    product_id = f"nbl{clean_name.replace(' ', '')[:30]}"
    base_code = product_id[3:]

    product_group_id = ld.get('productGroupID', product_id_from_file) or product_id
    description = ld.get('description', '').strip()
    features = details.get('features', [])
    composition = details.get('composition', '')
    if features:
        description += "\n" + " | ".join(features)

    full_text = (composition + " " + " ".join(features)).lower()
    upper_material, sole_material, closure_type, heel_drop = extract_materials(full_text)
    weight = extract_weight(composition) or extract_weight(" ".join(features))

    launch_price = details.get('launch_price')
    if launch_price is None:
        first_variant = ld.get('hasVariant', [{}])[0]
        launch_price = first_variant.get('offers', {}).get('price', 0)
    try:
        launch_price = float(launch_price) if launch_price else 0.0
    except:
        launch_price = 0.0

    top_images = get_image_style(json_data.get("images", []))
    variants = ld.get('hasVariant', [])

    for variant in variants:
        v_sku = variant.get('sku', '').strip()
        if not v_sku:
            continue

        size_str = variant.get('size', '').strip()
        if not size_str or not re.match(r'^\d+(\.\d+)?$', size_str):
            continue

        # ✅ Normalize size "16.0" == "16"
        try:
            size_val = float(size_str)
            size_str = str(int(size_val)) if size_val.is_integer() else str(size_val)
        except:
            pass

        size_clean = size_str
        size_name = f"US {size_str}"

        color_name = (variant.get('color', '') or "black").strip().lower()
        image_obj = variant.get('image', {})
        image_url = image_obj.get('url') if isinstance(image_obj, dict) else image_obj or ''

        cid = extract_cid_from_image(image_url)
        if not cid:
            cid = ''.join(word[0] for word in color_name.split()[:3])[:8]

        unique_key = f"{v_sku}|{cid}|{size_clean}"
        if unique_key in seen_combinations:
            print(f"⚠️ Duplicate skipped → {unique_key}")
            continue
        seen_combinations.add(unique_key)

        offers = variant.get('offers', {})
        price = float(offers.get('price', launch_price) or launch_price)
        availability = 'in_stock' if 'InStock' in str(offers.get('availability', '')) else 'out_of_stock'
        variant_url = offers.get('url', url)

        gender = get_gender_from_sku(v_sku)
        if gender == 'unisex' and file_gender and file_gender.lower() in ['male', 'female', 'kids']:
            gender = file_gender.lower()

        sku = f"{product_id}%p{base_code}c{cid}s{size_clean}"

        variant_images_raw = variant.get('image', [])
        if isinstance(variant_images_raw, dict):
            variant_images_raw = [variant_images_raw]
        images = get_image_style(variant_images_raw) if variant_images_raw else top_images

        entry = {
            "product_id": product_id,
            "sub_brand": None,
            "gender": gender,
            "age_group": get_age_group(gender),
            "age_range": get_age_range(gender),
            "date_of_scraping": parse_launch_date(today_str),
            "url": variant_url or url,
            "title": model_name.lower(),
            "description": description,
            "product_ref_code": product_group_id,
            "color_id": f"{product_id}%{cid}",
            "color_name": color_name,
            "color_ref_code": cid,
            "sku": sku,
            "size_name": size_name,
            "size_type": "US",
            "size_ref_code": None,
            "price": price,
            "launch_price": launch_price,
            "availability": availability,
            "sole_material": sole_material,
            "upper_material": upper_material,
            "closure_type": closure_type,
            "toe_shape": None,
            "heel_type": None,
            "weight": weight,
            "heel_to_toe_drop": heel_drop,
            "occasion": None,
            "origin": None,
            "images": images or []
        }
        all_products.append(entry)

    return all_products


def process_all_jsons():
    print(f"Scanning: {JSON_DATA_DIR}")
    if not os.path.exists(JSON_DATA_DIR):
        print("Folder NOT found!")
        return

    json_files = [f for f in os.listdir(JSON_DATA_DIR) if f.endswith('.json')]
    print(f"Found {len(json_files)} files")

    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client['tg_analytics_new_US']
    collection = db[f'crawler_sink_newbalance_{COUNTRY.lower()}_footwear']

    # ✅ Create unique compound index (prevents Mongo duplicates)
    try:
        collection.create_index(
            [("product_id", 1), ("color_ref_code", 1), ("size_name", 1)],
            unique=True,
            name="unique_product_color_size"
        )
        print("✅ MongoDB unique index ensured on (product_id, color_ref_code, size_name)")
    except Exception as e:
        print(f"⚠️ Could not create index: {e}")

    total = 0
    for file in json_files:
        path = os.path.join(JSON_DATA_DIR, file)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            file_gender = 'unisex'
            if 'women' in file.lower():
                file_gender = 'female'
            elif 'men' in file.lower():
                file_gender = 'male'
            elif 'kids' in file.lower():
                file_gender = 'kids'

            items = create_individual_json(TODAY_STR, data, file_gender)
            if items:
                # Safe insert (skip duplicates)
                for item in items:
                    try:
                        collection.insert_one(item)
                        total += 1
                    except pymongo.errors.DuplicateKeyError:
                        pass
                print(f"Inserted {len(items)} unique SKUs from {file}")
            else:
                print(f"Skipped {file} → no valid data")

        except Exception as e:
            print(f"ERROR {file}: {e}")
            traceback.print_exc()

    print(f"\nFINISHED! Total unique documents inserted: {total}")
    client.close()


if __name__ == "__main__":
    process_all_jsons()
