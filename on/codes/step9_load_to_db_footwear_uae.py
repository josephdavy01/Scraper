import os
import re
import json
import math
import pymongo
import traceback
from datetime import date, datetime

def parse_launch_date(date_string):
    format_string_with_ms = '%Y-%m-%dT%H:%M:%S.%fZ'
    format_string_without_ms = '%Y-%m-%dT%H:%M:%SZ'
    format_string_date_only_iso = '%Y-%m-%d'  
    format_string_date_only_us = '%m-%d-%Y' 
    
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            try:
                return datetime.strptime(date_string, format_string_date_only_iso)
            except ValueError:
                return datetime.strptime(date_string, format_string_date_only_us)


def calculate_original_price(pricing, badge_text):
    price = float(str(pricing.get("sale_price","0")).replace("Dhs.","").replace(",","").strip().split()[0])
    if not badge_text or "reduced" not in badge_text.lower():
        return price
    m = re.search(r"(\d+)", badge_text)
    if not m:
        return price
    pct = float(m.group(1))
    if pct >= 100:
        return price
    return math.ceil(price / (1 - pct/100) / 5) * 5
    
def is_footwear(j):
    return any(k in c.get("text", "").lower() 
               for c in j.get("navigation", {}).get("breadcrumbs", []) 
               for k in ("shoe", "shoes"))

def extract_heel_to_toe_drop(qf):
    return next((i.get("value") for i in qf
                 if "heel" in i.get("title","").lower() and "drop" in i.get("title","").lower()), None)

def extract_materials(material_data):
    if not material_data or not isinstance(material_data, dict):
        return None, None

    text = material_data.get("materials", "")
    if not text:
        return None, None
    upper, sole = None, None

    for part in text.split("/"):
        part = part.strip()
        if part.lower().startswith("upper unit:"):
            upper = part.split(":", 1)[1].strip()
        elif "outsole" in part.lower():
            sole = part.split(":", 1)[-1].strip()

    return upper, sole

def format_images(image_list):
    temp_styles = []
    for index, img_url in image_list.items():
        if index == "5":
            image_style = "n_f_f_c"
        else:
            image_style = "s0"

        temp_styles.append({
            "url": img_url,
            "image_style": image_style
        })
    return temp_styles

def extract_origin(material_data):
    s = (material_data or {}).get("supplier") or (material_data or {}).get("supplier_transparency")
    return s.split(",")[-1].strip() if s else None

def get_age_group(gender):
    gender = gender.lower()
    if gender in ['female', 'women', 'male', 'men']:
        return ['adult']
    if gender in ['kids', 'youth']:
        return ['kids']
    return ['adult']

def get_age_range(gender):
    gender = gender.lower()
    if gender in ['female', 'women', 'male', 'men']:
        return ['18y']
    if gender in ['kids', 'youth']:
        return ['1y', '17y']
    return ['18y']

def gender_map(gender):
    if not gender:
        return "unisex"
    g = gender.strip().lower()
    if g in ("youth", "kids", "kid", "children"):
        return "kids"
    elif g in ("women", "womens", "woman", "female"):
        return "female"
    elif g in ("men", "mens", "man", "male"):
        return "male"
    else:
        return "unisex"

def create_individual_json(today_str, json_data, gender):
    all_products = []
    
    if not json_data or not isinstance(json_data, dict):
        return []
    
    if not is_footwear(json_data):
        return []
    
    sku = json_data.get("basic_info", {}) \
               .get("current_variant", {}) \
               .get("sku", "")
    base_sku = sku.split()[0].strip() if sku else ""
    product_group_id = base_sku[:7]

    if not product_group_id or not base_sku:
        print(f"Skipping product - missing required fields: product_group_id={product_group_id}, sku={base_sku}")
        return []
    
    title = json_data.get("basic_info", {}).get("current_variant", "").get("name", "").split(' - ')[0].lower().strip()
    url = json_data.get("product_url", "")
    if url == '':
        vid = json_data.get("basic_info", {}).get("current_variant", {}).get("id", "")
        url = f"https://on.ae/products/{title.replace(' ', '-').replace('/', '-')}?variant={vid}"

    json_gender = json_data.get("product_options", {}).get("gender_selected", "")
    if json_gender:
        gender = json_gender.lower().strip()
    else:
        gender = "unisex"
        
    product_id = f'onb{product_group_id}'
    description = json_data.get("basic_info", {}).get("description", "")
    cid = base_sku.replace(product_id, "").strip()
    material_data = json_data.get('additional_info', {}).get('materials', {})
    upper,sole = extract_materials(material_data)
    origin_val = extract_origin(material_data) if material_data else None
    origin = origin_val.lower().strip() if origin_val else None
    images = json_data.get("images", [])

    if not isinstance(images, (dict, list)) or len(images) == 0:
        return []
    try:
        price = float(str(json_data.get("pricing", {}).get("sale_price", "0"))
                    .replace("Dhs.", "").replace(",", "").split()[0])
    except (ValueError, TypeError):
        price = 0.0

    badge_text = json_data.get("basic_info", {}).get("badge", "")
    key_features = json_data.get("additional_info", {}).get("key_features", [])
    if key_features:
        description += '\n' + ' | '.join(key_features)
    quick_facts = json_data.get("additional_info", {}).get("quick_facts", [])
    heel_drop = extract_heel_to_toe_drop(quick_facts)

    
    sizes = json_data.get("product_options", {}).get("sizes", [])
    if not sizes:
        print(f"Skipping product {product_id} - no sizes available")
        return []

    for size_info in sizes:
        if not isinstance(size_info, dict):
            continue

        size_name = size_info.get("size", "")
        size_availability = bool(size_info.get("available", False))
        if size_availability:
            availability = "in_stock"
        else:
            availability = "out_of_stock"
        
        size_specific_sku = f'{product_id}%{base_sku}s{size_name}'
        color_name = json_data.get("basic_info", {}).get("current_variant", {}).get("option2", "").lower().strip()
        
        entry = {
            "product_id": product_id,
            "sub_brand": None,
            "gender": gender_map(gender),
            "age_group": get_age_group(gender),
            "age_range": get_age_range(gender),
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title":title,
            "description": description,
            "product_ref_code": product_group_id,
            "color_id": f'{product_id}%{cid}',
            "color_name": color_name,
            "color_ref_code": cid,
            "sku": size_specific_sku,
            "size_name": size_name,
            "size_ref_code": None,
            "price": price,
            "launch_price": calculate_original_price(json_data.get("pricing", {}), badge_text),
            "availability": availability,
            "sole_material": sole,
            "upper_material": upper,
            "closure_type": None,
            "toe_shape": None,
            "heel_type": None,
            "weight": None,
            "heel_to_toe_drop": heel_drop,
            "occasion": None,
            "origin": origin,
            "images":format_images(images)
        }
        all_products.append(entry)
    return all_products

def get_folders(sub_folders, exclude_folder=None):
    if exclude_folder is None:
        exclude_folder = []
    if not os.path.exists(sub_folders):
        return []
        
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    return [folder for folder in folders if '.json' not in folder]

def process_jsons(today_str, country,collection):
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = get_folders(gender_folder, [])
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, [])
        for category in categories:
            file_folder = os.path.join(category_folder, category)
            files = os.listdir(file_folder)
            for file in files:
                file_path = os.path.join(file_folder, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    skus = create_individual_json(today_str, data, gender)
                    if skus:
                        collection.insert_many(skus)
                        for sku in skus:
                            print(f'Product_id: {sku["product_id"]}, SKU: {sku["sku"]}')
                    else:
                        print(f"Skipping {file_path} - not footware or missing data")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-05'
    
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    
    countries = ['UAE']

    for country in countries:
        collection = db[f'crawler_sink_on_{country.lower()}_footwear']
        print(f"Processing {country} footwaear...")
        process_jsons(today_str, country, collection)
        print(f"Footware data loading for {country} completed!")
        
    client.close()