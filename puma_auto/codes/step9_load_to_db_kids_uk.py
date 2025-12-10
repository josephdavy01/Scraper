import os
import re
import json
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
    for img_url in image_list:
        image_style = "s0"
        temp_styles.append({"url": img_url, "image_style": image_style})
    return temp_styles

def extract_color(color_info):
    for item in color_info:
        if item.startswith("Color:") or item.startswith("Colour:"):
            return item.split(":", 1)[1].strip().lower()
    return None

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

def get_age_range(size):
    if '(' in size:
        size = size.split('(')[0].strip()
    size = size.lower().replace('slim', '').replace('long', '').replace('plus', '').replace('1.5', '18 months').replace(' - ', '-').replace(' m', 'm').replace(' y', 'y').strip()

    age_range = []
    size_part = size.split(' ')[-1]
    
    if 'y' in size_part or 'm' in size_part:
        if 'm' in size_part and 'y' in size_part:
            mage = int(re.search(r'(\d+)m', size_part).group(1))
            yage = int(re.search(r'(\d+)y', size_part).group(1))
            age_range = [f'{mage}m', f'{yage}y']
        elif 'y' in size_part:
            nums = re.findall(r'\d+', size_part)
            age_range = [f'{n}y' for n in nums]
        elif 'm' in size_part:
            nums = re.findall(r'\d+', size_part)
            age_range = [f'{n}m' for n in nums]
    
    return remap_age_range(age_range)

def remap_age_range(age_range):
    if len(age_range) > 1:
        if age_range[1] == '2y' and 'm' in age_range[0]:
            return [age_range[0], '24m']
        elif age_range[0] == '1y':
            return ['12m', age_range[1]]
    return age_range

def get_age_group(age_range):
    if not age_range:
        return ['adult']

    age_map = {
        'new_born': [f'{i}m' for i in range(7)],
        'baby':     [f'{i}m' for i in range(7, 25)],
        'junior':   [f'{i}y' for i in range(2, 8)],
        'senior':   [f'{i}y' for i in range(8, 13)],
        'teen':     [f'{i}y' for i in range(13, 18)],
        'adult':    ['18y']
    }
    age_group_order = ['new_born', 'baby', 'junior', 'senior', 'teen', 'adult']
    
    start_age, end_age = age_range[0], age_range[-1]
    
    s_index, e_index = -1, -1
    for i, group in enumerate(age_group_order):
        if start_age in age_map[group]:
            s_index = i
        if end_age in age_map[group]:
            e_index = i
            
    if s_index != -1 and e_index != -1:
        return age_group_order[s_index : e_index + 1]

    return ['adult']


def create_individual_json(today_str, json_data):
    all_products = []
    if not json_data: return []
    
    if not is_apparel(json_data): return []

    mapped_gender = gender_map(json_data)
    
    url = json_data.get("product_url", "")
    match = re.search(r'/pd/[^/]+/(\d+)', url)
    product_ref_code = match.group(1) if match else None

    style_color_list = json_data.get("style_color", [])
    base_sku = next((item.split("Style:")[1].strip() for item in style_color_list if item.startswith("Style:")), None)
    
    if not product_ref_code or not base_sku:
        return []

    title = json_data.get("title", "").lower().strip()
    style_parts = base_sku.split('_')
    cid = style_parts[1] if len(style_parts) > 1 else style_parts[0]

    original_price_str = json_data.get("original_price", "")
    sale_price_str = json_data.get("sale_price", "")
    
    try:
        price = float(re.sub(r'[^\d.]', '', sale_price_str or original_price_str or '0'))
        launch_price = float(re.sub(r'[^\d.]', '', original_price_str or '0'))
        if not launch_price or launch_price < price:
            launch_price = price
    except (ValueError, TypeError):
        price, launch_price = 0.0, 0.0
    
    product_id = f'pum{product_ref_code}'
    description = f"{json_data.get('description', '')} {' '.join(json_data.get('features_benefits', []))} {' '.join(json_data.get('product_details', []))}"
    
    composition_string = json_data.get("material_info", {})
    composition = ", ".join([f"{key}: {value}" for key, value in composition_string.items()]) if composition_string else None

    color_name = extract_color(style_color_list)
   
    origin = (json_data.get("country_of_origin") or "").lower().strip() or None
    image_list = json_data.get("images", [])
    sizes = json_data.get("sizes", [])

    if not sizes: return []

    kids_size_pattern = re.compile(r"^\d{1,2}(-\d{1,2})?[my]$")

    for size_info in sizes:
        if not isinstance(size_info, str): continue
        
        if size_info in ["OSFA","Select Size","One Size","UA","Adult","S/M","Youth"]:
                continue

        size_clean = size_info.lower().strip()
        sold_out = (size_clean == "Sold Out" or "sold out" in size_clean)

        if kids_size_pattern.match(size_clean):

            if price == 0:
                print(f"Skipping sku {size_info} price is zerooo")
                continue

            age_range = get_age_range(size_info)
            age_group = get_age_group(age_range)
            
            size_specific_sku = f'{product_id}%{base_sku}s{size_info}'
            availability = "out_of_stock" if sold_out else "in_stock"
            
            entry = {
                "product_id": product_id,
                "gender": mapped_gender,
                "age_group": age_group,
                "age_range": age_range,
                "date_of_scraping": parse_launch_date(today_str),
                "url": url,
                "title": title,
                "description": description,
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

def get_folders(sub_folders):
    if not os.path.exists(sub_folders): return []
    return [d for d in os.listdir(sub_folders) if os.path.isdir(os.path.join(sub_folders, d))]

def process_jsons(current_date, country, collection):
    base_folder = os.path.join(country, 'Data', current_date, 'Json_data')
    for gender in get_folders(base_folder):
        
        for category in get_folders(os.path.join(base_folder, gender)):
            file_folder = os.path.join(base_folder, gender, category)
            for file_name in os.listdir(file_folder):
                if not file_name.endswith('.json'): continue
                
                file_path = os.path.join(file_folder, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    skus = create_individual_json(current_date, data)
                    
                    if skus:
                        collection.insert_many(skus)
                        print(f"Inserted {len(skus)} SKUs from {file_name}")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()

if __name__ == "__main__":

    today_str = date.today().strftime('%Y-%m-%d')
    # today_str='2025-12-06'

    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    
    countries = ['UK']  # You can add more countries as needed
    for country in countries:
    
        collection = db[f'crawler_sink_puma_{country.lower()}_kids']
        print(f"\n--- Processing {country} for date: {today_str} ---")
        process_jsons(today_str, country, collection)
        print(f"--- Data loading for {country} on {today_str} completed! ---")
    client.close()