import os
import re
import json
import math
import pymongo
import traceback
from datetime import date, datetime


def get_product_text(j):
    return f"{j.get('product_url', '')} {j.get('title', '')} {j.get('subtitle', '')} {' '.join(j.get('breadcrumbs', []))}".lower()

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

def is_apparel(j):
    j_lower = get_product_text(j)

    footwear_keywords = (
    "shoe", "shoes", "sneaker", "sneakers", "boots", "boot", "loafer", "loafers","flipflop", "flip-flops", "flip flop", "slipper", "slippers","slide", "slides", "sandal", "sandals", "clog", "clogs",
    "high-top", "high top","low-top", "low top","sockfootwear","footwear","footwears"
    )

    accessory_keywords = (
    "bag", "flask", "backpack", "backpacks", "cap", "hat", "beanie", "scarf", "gloves", "socks", "belt", "wallet",
    "accessories", "crown", "ball","towel","mask", "facemask", "balaclava", "headband", "waterbottle", "water bottle", "shaker", "bottle", "bat",
    "resistance band", "wristband", "umbrella", "shopper", "tote", "armband", "visor", "gym sack", "sack","headwear"
    )

    if any(keyword in j_lower for keyword in footwear_keywords):
        return False
    if any(keyword in j_lower for keyword in accessory_keywords):
        return False
    return True

def format_images(image_list):
    temp_styles = []
    for index, img_url in enumerate(image_list):
        
        image_style = "s0"

        temp_styles.append({
            "url": img_url,
            "image_style": image_style
        })
    return temp_styles


def extract_color(color_info):
    for item in color_info:
        if item.startswith("Color:") or item.startswith("Colour:"):
            return item.split(":", 1)[1].strip().lower()
    return None


def get_age_group(mapped_gender):
    gender = mapped_gender.lower()
    if gender in ['female', 'women', 'male', 'men']:
        return ['adult']
    if gender in ['kids', 'youth']:
        return ['kids']
    return ['adult']


def get_age_range(mapped_gender):
    gender = mapped_gender.lower()
    if gender in ['female', 'women', 'male', 'men']:
        return ['18y']
    if gender in ['kids', 'youth']:
        return ['1y', '17y']
    return ['18y'] 

def gender_map(j):

    text = get_product_text(j)
    kids_keywords = (
        "kids", "kid", "children", "youth", "toddler", "toddlers", "baby", "minicats", "infant", "infants",
        "junior", "juniors", "preschool", "pre-school", "nursery", "little", "big kid", "small kid", "preteen"
    )
    is_kids = any(keyword in text for keyword in kids_keywords)

    if not is_kids:
        if any(keyword in text for keyword in ("women", "women's", "womens", "female")):
            return "female"
        if any(keyword in text for keyword in ("men", "mens", "men's", "male")):
            return "male"
        return "unisex"
    
    if any(keyword in text for keyword in ("girls", "girl")):
        return "female"
    if any(keyword in text for keyword in ("boys", "boy")):
        return "male"
    return "unisex"

def gender_map_kids(j): 
    text = get_product_text(j)
    if any(keyword in text for keyword in ("kids", "kid", "children", "youth", "toddler", "toddlers", "baby", "minicats", "infant", "infants",
        "junior", "juniors", "preschool", "pre-school", "nursery", "little", "big kid", "small kid", "preteen")):

        return "kids"
    if any(keyword in text for keyword in ("women", "women's", "womens", "female")):
        return "female"
    if any(keyword in text for keyword in ("men", "mens", "men's", "male")):
        return "male"
    return "unisex"


def create_individual_json(today_str, json_data, gender):
    all_products = []
    if not json_data or not isinstance(json_data, dict):
        return []
    
    product_text = get_product_text(json_data)
    
    is_kids_product = any(keyword in product_text for keyword in ("kids", "kid", "children", "youth", "toddler", "toddlers", "baby", "minicats", "infant", "infants",
        "junior", "juniors", "preschool", "pre-school", "nursery", "little", "big kid", "small kid", "preteen"))
    
    if is_kids_product:
        print(f"Skipping kids' product: {json_data.get('title', 'No Title')}")
        return []
    
    if not is_apparel(json_data):
        return []
    
    url = json_data.get("product_url", "")
    match = re.search(r'/pd/[^/]+/(\d+)', url)
    if match:
        product_ref_code = match.group(1)
    else:
        print("Could not extract product reference code from URL")
        return []

    style_color_list = json_data.get("style_color", [])
    base_sku = "unknown"
    for item in style_color_list:
        if item.startswith("Style:"):
            base_sku = item.split("Style:")[1].strip()
            break
    
    if not product_ref_code or base_sku == "unknown":
        print(f"Skipping product - missing required fields: product_ref_code={product_ref_code}, sku={base_sku}")
        return []
    
    title = json_data.get("title", "").lower().strip()

    mapped_gender = gender_map_kids(json_data)
    gender = gender_map(json_data)
    
    cid = ""
    for item in style_color_list:
        if item.startswith("Style:"):
            style_parts = item.split("Style:")[1].strip().split("_")
            if len(style_parts) > 1:
                cid = style_parts[1]
            else:
                cid = style_parts[0]
            break

    original_price_str = json_data.get("original_price", "")
    sale_price_str = json_data.get("sale_price", "")
    
    try:
        price = float(re.sub(r'[^\d.]', '', sale_price_str or original_price_str or '0'))
        launch_price = float(re.sub(r'[^\d.]', '', original_price_str or '0'))
        if launch_price == 0 or launch_price < price:
            launch_price = price
    except (ValueError, TypeError):
        price = 0.0
        launch_price = 0.0
    
    product_id = f'pum{product_ref_code}'
    
    description = json_data.get("description", "")
    features = json_data.get("features_benefits", [])
    product_details=json_data.get("product_details", [])
    
    full_description = description + " " + " ".join(features) + " " + " ".join(product_details)
    

    composition_string = json_data.get("material_info", {})
    composition = ", ".join([f"{key}: {value}" for key, value in composition_string.items()]) if composition_string else None
    
    color_name = extract_color(style_color_list)
    
    origin = json_data.get("country_of_origin", "").lower().strip() if json_data.get("country_of_origin") else None
    image_list = json_data.get("images", [])
    
    sizes = json_data.get("sizes", [])
    if not sizes or not isinstance(sizes, list):
        print(f"Skipping product {product_id} - no sizes available")
        return []
    
    kids_size_pattern = re.compile(r"^\d{1,2}(-\d{1,2})?[my]$")
    
    for size_info in sizes:
        
        if not isinstance(size_info, str) or size_info in ["OSFA","Select Size","One Size","UA","Adult","S/M","Youth"]:
            continue
        
        size_clean = size_info.lower().strip()
        if size_clean == "sold out":
            availability = "out_of_stock"
        else:
            availability = "in_stock"
            
        if kids_size_pattern.match(size_clean):
            print(f"Skipping product '{title}' because it has a kids' size: {size_info}")
            return []
        
        if price == 0:
            print(f"Skipping sku {size_info} price is zerooo")
            continue
        
        size_specific_sku = f'{product_id}%{base_sku}s{size_info}'
        
        entry = {
            "product_id": product_id,
            "gender": gender,
            "age_group": get_age_group(mapped_gender),
            "age_range": get_age_range(mapped_gender),
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": title,
            "description": full_description,
            "product_ref_code": product_ref_code,
            "color_id": f'{product_id}%{cid}',
            "color_name": color_name,
            "color_ref_code": cid,
            "sku": size_specific_sku,
            "size_name": size_info,
            "size_ref_code": None,
            "price": price,
            "launch_price": launch_price,
            "availability": availability,
            "demand": None,
            "composition": composition,
            "origin": origin,
            "images": format_images(image_list),
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


def process_jsons(today_str, country, collection):
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
                        print(f"Skipping {file} - not apparel or missing data")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()


if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str='2025-12-08'

    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    
    countries = ['INDIA']

    for country in countries:
        collection = db[f'crawler_sink_puma_{country.lower()}']
        print(f"Processing {today_str} apparel...")
        process_jsons(today_str, country, collection)
        print(f"Apparel data loading for {country} completed!")
        
    client.close()
