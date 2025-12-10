import os
import re
import math
import json
import pymongo
import traceback
import pandas as pd
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

def calculate_original_price(price, badge_text):
    if not badge_text:
        return price
    
    badge_lower = badge_text.lower().strip()
    if 'reduced' in badge_lower:
        import re
        number_match = re.search(r'(\d+)', badge_lower)
        
        if number_match:
            discount_percentage = float(number_match.group(1))
            if discount_percentage >= 100:
                return price
            launch_price = price / (1 - discount_percentage/100)
            return math.ceil(launch_price / 5) * 5
        else:
            return price
    return price

def extract_weight_from_features(key_features):
    if not key_features:
        return None
    
    for feature in key_features:
        feature_lower = feature.lower()
        weight_match = re.search(r'weight[:\s]*(\d+(?:\.\d+)?)\s*g', feature_lower)
        if weight_match:
            return f"{weight_match.group(1)}g" 
    return None
    
def clean_product_name(product_name):
    if not product_name:
        return product_name
    name = product_name.strip()
    prefixes_to_remove = ["men's ", "women's ", "mens ", "womens ", "Women's", "Men's "]
    
    for prefix in prefixes_to_remove:
        if name.lower().startswith(prefix.lower()):
            return name[len(prefix):].strip()
    
    return name

def is_footwear(json_data):
    variant_url = json_data.get('variant_url', '').lower()
    footware_keywords = ['shoes', 'shoe']
    return any(keyword in variant_url for keyword in footware_keywords)

def extract_heel_to_toe_drop(quick_facts):
    if not quick_facts or not isinstance(quick_facts, dict):
        return None
    heel_drop = quick_facts.get('heel_to_toe_drop')
    if heel_drop:
        return str(heel_drop)
    for key in quick_facts.keys():
        if 'heel' in key.lower() and 'drop' in key.lower():
            return str(quick_facts[key])
    return None

def extract_upper_material(material_data):
    if not material_data:
        return None
    
    if isinstance(material_data, dict):
        materials = material_data.get('materials', [])
        if materials and isinstance(materials, list):
            return '; '.join(materials)
        return None
    elif isinstance(material_data, str):
        return material_data
    return None

def extract_origin(material_data):
    if not material_data or not isinstance(material_data, dict):
        return None
    supplier = material_data.get('supplier')
    if supplier:
        if ',' in supplier:
            parts = supplier.split(',')
            return parts[-1].strip()
        return supplier.strip()
    return None

def remap_gender(gender):
    if gender in ['women', 'female']:
        return 'female'
    elif gender in ['men', 'male']:
        return 'male'
    elif gender in ['kids', 'shop_all']:
        return 'kids'
    return 'unisex'

def get_age_group(gender):
    if gender in ['female', 'male']:
        return ['adult']
    if gender in ['kids']:
        return ['kids']
    return ['adult']

def get_age_range(gender):
    if gender in ['female', 'male']:
        return ['18y']
    if gender in ['kids']:
        return ['1y', '17y']
    return ['18y']

def clean_size_name(size_name):
    if not size_name:
        return ""
    size = size_name
    for pattern in ['Only', 'No items', 'Notify me']:
        size = size.split(pattern)[0]
    
    return size.strip()

def get_image_style(images):
    temp_styles = []
    for index, img_url in images.items():
        if index == "5":
            image_style = "n_f_f_c"
        else:
            image_style = "s0"

        temp_styles.append({
            "url": img_url,
            "image_style": image_style
        })
    return temp_styles

def create_individual_json(today_str, json_data, gender):
    all_products = []
    
    if not json_data or not isinstance(json_data, dict):
        return []
    
    if not is_footwear(json_data):
        return []
    
    product_group_id = json_data.get('product_group_id', '').strip()
    base_sku = json_data.get('sku', '').strip()
    if not product_group_id:
        if '.' in base_sku:
            product_group_id = base_sku.split('.')[0]
        else : product_group_id = base_sku[:-4]
    
    if not product_group_id or not base_sku:
        print(f"Skipping product - missing required fields: product_group_id={product_group_id}, sku={base_sku}")
        return []
    
    name = clean_product_name(json_data.get('product_name', '')).lower()
    url = json_data.get('variant_url', '') or json_data.get('category_url', '')
    
    json_gender = json_data.get('gender')
    if json_gender:
        gender = remap_gender(json_gender.lower())
    else:
        gender = remap_gender(gender.lower() if gender else 'unisex')
        
    product_id = f'onb{product_group_id}'
    description = json_data.get('description', '')
    cid = base_sku.replace(product_group_id, '').strip()
    material_data = json_data.get('material')
    composition = extract_upper_material(material_data)
    origin_raw = extract_origin(material_data)
    origin = origin_raw.lower() if origin_raw else None
    images = get_image_style(json_data.get('all_images', []))
    if not isinstance(images, (dict, list)) or len(images) == 0:
        return []
    try:
        price = float(json_data.get('price', 0))
    except (ValueError, TypeError):
        price = 0.0
    badge_text = json_data.get('badge', '')
    key_features = json_data.get('key_features', [])
    if key_features:
        description += '\n' + ' | '.join(key_features)
    quick_facts = json_data.get('quick_facts', {})
    heel_drop = extract_heel_to_toe_drop(quick_facts)
    
    
    sizes = json_data.get('sizes', [])
    if not sizes:
        print(f"Skipping product {product_group_id} - no sizes available")
        return []
    
    for size_info in sizes:
        if not isinstance(size_info, dict):
            continue
            
        size_name = size_info.get('size_name', '')
        size_availability = size_info.get('in_stock', True)
        
        size = clean_size_name(size_name)
        if not size:
            continue
        size_specific_sku = f'{product_id}%{base_sku}s{size}'
        availability = 'in_stock' if size_availability else 'out_of_stock'
        color_name = json_data.get('color_name', '').strip().lower()
        
        entry = {
            "product_id": product_id,
            "sub_brand": None,
            "gender": gender,
            "age_group": get_age_group(gender),
            "age_range": get_age_range(gender),
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title":name,
            "description": description,
            "product_ref_code": product_group_id,
            "color_id": f'{product_id}%{cid}',
            "color_name": color_name,
            "color_ref_code": cid,
            "sku": size_specific_sku,
            "size_name": size,
            "size_ref_code": None,
            "price": price,
            "launch_price": calculate_original_price(price, badge_text),
            "availability": availability,
            "sole_material": None,
            "upper_material": composition,
            "closure_type": None,
            "toe_shape": None,
            "heel_type": None,
            "weight": extract_weight_from_features(key_features),
            "heel_to_toe_drop": heel_drop,   
            "occasion": None,
            "origin": origin,
            "images": images
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


def process_jsons( today_str, country,collection):
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
                        print(f"Skipping {file} - not footware or missing data")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-05'
    
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    
    countries = ['USA']
    
    for country in countries:
        collection = db[f'crawler_sink_on_{country.lower()}_footwear']
        print(f"Processing {country} footwaear...")
        process_jsons( today_str, country, collection)
        print(f"Footware data loading for {country} completed!")
    
    client.close()