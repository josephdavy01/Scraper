import os
import re
import json
import pymongo
import traceback
from datetime import date, datetime, timezone

EXCLUDED_KEYWORDS = [
    "hat", "cap", "sock", "beanie", "headband", "crew", "glove"
]

def get_gender_from_url(url: str):
    url = url.lower()

    if "womens" in url:
        return "female"
    
    elif "mens" in url:
        return "male"
    
    elif "unisex" in url:
        return "unisex"
    else:
        return None  

def is_excluded_product(title: str) -> bool:
    if not title:
        return False
    title_lower = title.lower()
    for word in EXCLUDED_KEYWORDS:
        pattern = r'\b' + re.escape(word) + r's?\b'
        if re.search(pattern, title_lower):
            return True
    return False

def parse_launch_date(today_str):
    dt = datetime.strptime(today_str, "%Y-%m-%d")
    dt = dt.replace(tzinfo=timezone.utc)
    return dt 

def is_running_sock(category: str) -> bool:
    if not category:
        return False
    return "running sock" in category.lower()

def get_image_style(image_list):
    styled_images = []
    for img in image_list:
        img_lower = img.lower()
        if "-l-" in img_lower or "-lf-" in img_lower:
            styled_images.append({"url": img, "image_style": "s0"})
        else:
            styled_images.append({"url": img, "image_style": "s0"})
    return styled_images

def create_individual_json(today_str, json_data):
    all_products = []
    if not json_data or not isinstance(json_data, dict):
        return []
    url = json_data.get("url", "")
    gender = get_gender_from_url(url)
    if not gender:
        print("Skipping, gender not found in URL")
        return []
    name = json_data.get("jsonld_data", {}).get("name", "").strip()
    category = json_data.get("jsonld_data", {}).get("category", "")
    if is_excluded_product(name):
        print(f"Skipping - excluded item ({name})")
        return []
    if is_running_sock(category):
        print("Skipping - running sock in category")
        return []
    sizes = json_data.get("sizes", [])
    if not sizes:
        print("Skipping - sizes empty")
        return []
    if any(s.get("size_type", "").lower() != "shoe" for s in sizes):
        print("Skipping - apparel product found in sizes")
        return []
    prdt_id = json_data.get("jsonld_data", {}).get("sku", "")
    if prdt_id:
        if '.' in prdt_id:
            numeric_part = prdt_id.split('.')[0] 
            corrected_id = numeric_part[:6]
        else:
            corrected_id = prdt_id

    product_id = 'bro' + corrected_id
    cid = json_data.get('color_info', {}).get('color_id', '')
    color_name = json_data.get('color_info', {}).get('color_name', '').lower()
    images = get_image_style(json_data.get('jsonld_data', {}).get('image', []))
    weight = json_data.get("specs",{}).get("weight").split("/")[1].strip() if json_data.get("specs",{}).get("weight", None) else None
    heel_to_toe_drop = json_data.get("specs",{}).get("heel_to_toe_drop", None)
    occasion = json_data.get("specs",{}).get("Designed for", None).lower()
    price = json_data.get("price_info", {}).get("sale_price", None)
    launch_price = json_data.get("price_info", {}).get("original_price", None)
    if launch_price is None and price is not None:
        launch_price = price
    full_desc = json_data.get("full_description", "")
    features = json_data.get("features", [])
    best_for = json_data.get("occasion", [])
    description = full_desc
    if features:
        description += " | " + " | ".join(features)
    if best_for:
        description += " | " + " | ".join(best_for)
    for size_obj in sizes:
        size_name = size_obj.get("size", "").strip()
        if not size_name:
            continue
        availability = "in_stock" if size_obj.get("in_stock", False) else "out_of_stock"
        safe_size = re.sub(r'[^A-Za-z0-9]', '', size_name).upper()
        size_specific_sku = f"{product_id}%p{corrected_id}c{cid}s{safe_size}"
        if price is None:
            print(f"Skipping {product_id} size {size_name} - price is null")
            continue
        entry = {
            "product_id": product_id,
            "sub_brand": None,
            "gender": gender,
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": name.lower(),
            "description": description,
            "product_ref_code": None,
            "color_id": f'{product_id}%{cid}',
            "color_name": color_name,
            "color_ref_code": cid,
            "sku": size_specific_sku,
            "size_name": size_name,
            "size_ref_code": None,
            "price": price,
            "launch_price": launch_price,
            "availability": availability,
            "sole_material": None,
            "upper_material": None,
            "occasion": occasion,
            "closure_type": None,
            "toe_type": None,
            "heel_type": None,
            "weight": weight,
            "heel_to_toe_drop": heel_to_toe_drop,
            "origin": None,
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
                        print(f"Skipping {file_name} - not shoe or missing data")
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-11-19'
    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client['tg_analytics']
    countries = ['UK', 'USA']
    for country in countries:
        collection = db[f'crawler_sink_brooks_{country.lower()}_footwear']
        print(f"Processing {country} footwear...")
        data_path = os.path.join(country, 'Data')
        if not os.path.exists(data_path):
            continue
        for today_subfolder in os.listdir(data_path):
            process_jsons(today_subfolder, country, collection)
        print(f"Footwear data loading for {country} completed!")
    client.close()
