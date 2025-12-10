import os
import re
import json
import math
import pymongo
import traceback
from datetime import date, datetime

def get_product_text(j):
    return f"{j.get('product_url', '')} {j.get('title', '')} {j.get('subtitle', '')} {' '.join(j.get('breadcrumbs', []))}".lower()

def is_footwear(j):
    keywords = (
        "shoe", "shoes", "sneaker", "sneakers", "boots", "boot", "loafer", "loafers",
        "flipflop", "flip-flops", "flip flop", "slipper", "slippers", "slide", "slides",
        "sandal", "sandals", "clog", "clogs", "high-top", "high top", "low-top", "low top",
        "sockfootwear", "footwear", "footwears"
    )

    accessory_keywords = (
        "bag", "flask", "backpack", "backpacks", "cap", "hat", "beanie", "scarf", "gloves",
        "socks", "belt", "wallet", "accessories", "crown", "ball", "towel", "mask",
        "facemask", "balaclava", "headband", "waterbottle", "water bottle", "shaker",
        "bottle", "bat", "resistance band", "wristband", "umbrella", "shopper", "tote",
        "armband", "visor", "gym sack", "sack", "headwear"
    )

    text = get_product_text(j)

    if any(k in text for k in accessory_keywords):
        return False

    return any(k in text for k in keywords)

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


def extract_materials(json_data):
    material_info_raw = json_data.get("material_info", {}) or {}
    material_info = {str(k).strip().lower(): (v.strip() if isinstance(v, str) else v)
                     for k, v in material_info_raw.items()}

    def get_any(d, keys):
        for k in keys:
            v = d.get(k.lower())
            if v:
                return re.sub(r'[\\s\\.]$', '', str(v)).strip()
        return None

    upper = get_any(material_info, ["upper"])
    sole = get_any(material_info, ["outsole", "outer sole", "sole"])
    closure_from_material = get_any(material_info, ["closure", "fastener"])
    heel_drop_from_material = get_any(material_info, ["heel-to-toe drop", "heel to toe drop", "drop"])

    product_details = json_data.get("product_details", []) or []
    description = json_data.get("description", "") or ""
    features = json_data.get("features_benefits", []) or []

    def split_kv(line):
        parts = line.split(":", 1)
        if len(parts) == 2:
            key = parts[0].strip().lower()
            val = parts[1].strip().rstrip(".").strip()
            return key, val
        return None, None
    for detail in product_details:
        key, val = split_kv(detail)
        if not key or not val:
            continue
        if not upper and key in ("main material", "upper", "textile upper", "upper material"):
            if key == "textile upper":
                upper = "Textile"
            else:
                upper = val
        if not sole and (key in ("outer sole", "outsole")):
            sole = val

    closure = None
    text_for_closure = " ".join(product_details + [description] + features).lower()

    if not closure:
        for detail in product_details:
            k, v = split_kv(detail)
            if k and "closure" in k and v:
                closure = v.lower()
                break
    if not closure:
        if "lace-up" in text_for_closure or "lace up" in text_for_closure or "lace closure" in text_for_closure or "laced" in text_for_closure:
            closure = "lace-up"
        elif any(x in text_for_closure for x in ["hook-and-loop", "hook and loop", "hook & loop", "velcro"]):
            closure = "hook-and-loop"
    toe = None
    for detail in product_details:
        if "toe type:" in detail.lower():
            toe = detail.split(":", 1)[-1].strip().rstrip(".")
            break
    weight = None
    full_text = " ".join(product_details + [description] + features).lower()
    m = re.search(r'weight\\s*:\\s*([^,;\\n]+)', full_text, flags=re.I)
    if m:
        candidate = m.group(1).strip()
        weight = candidate
    else:
        m2 = re.search(r'(\\d+(?:\\.\\d+)?)\\s*(g|grams|oz|ounces)\\b', full_text, flags=re.I)
        if m2:
            weight = (m2.group(1) + " " + m2.group(2)).strip()

    heel_drop = heel_drop_from_material
    if not heel_drop:
        m3 = re.search(r'heel[-\\s]?to[-\\s]?toe[-\\s]?drop\\s*:\\s*([0-9]+(?:\\.[0-9]+)?\\s*mm)', full_text, flags=re.I)
        if m3:
            heel_drop = m3.group(1).replace(" ", "")
            heel_drop = re.sub(r'mm$', ' mm', heel_drop)
        else:
            m4 = re.search(r'heel[-\\s]?to[-\\s]?toe[-\\s]?drop[^\\d]*([0-9]+(?:\\.[0-9]+)?\\s*mm)', full_text, flags=re.I)
            if m4:
                heel_drop = m4.group(1).replace(" ", "")
                heel_drop = re.sub(r'mm$', ' mm', heel_drop)
    if not closure and closure_from_material:
        closure = closure_from_material.lower()

    return sole, upper, closure, toe, weight, heel_drop


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
    
    if not is_footwear(json_data):
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

    sole, upper, closure, toe, weight, heel_drop = extract_materials(json_data)
    
    original_price_str = json_data.get("original_price", "")
    sale_price_str = json_data.get("sale_price", "")
    
    try:
        price = float(re.sub(r'[^\d.]', '', sale_price_str or original_price_str or '0'))
        launch_price = float(re.sub(r'[^\d.]', '', original_price_str or '0'))
        if launch_price == 0:
            launch_price = price
    except (ValueError, TypeError):
        price = 0.0
        launch_price = 0.0
    
    product_id = f'pum{product_ref_code}'
    description = json_data.get("description", "")
    
    color_name = extract_color(style_color_list)
    
    origin = json_data.get("country_of_origin", "").lower().strip() if json_data.get("country_of_origin") else None
    image_list = json_data.get("images", [])
    
    sizes = json_data.get("sizes", [])

    if not sizes or not isinstance(sizes, list):
        print(f"Skipping product {product_id} - no sizes available")
        return []

    for size_info in sizes:
        if not isinstance(size_info, str):
            continue

        if all(isinstance(s, str) and re.match(r'^\d{1,2}-\d{1,2}Y$', s.strip()) for s in sizes):
            print(f"Skipping product {product_id} - sizes match kids clothing pattern")
            return []


        size_clean = size_info.lower().strip()
        if size_clean == "sold out":
            availability = "out_of_stock"
        else:
            availability = "in_stock"
        
        if size_info in ["OSFA","Select Size","One Size","UA","Adult","S/M","Youth"]:
            continue

        if price == 0:
            print(f"Skipping sku {size_info} price is zerooo")
            continue
        
        size_specific_sku = f'{product_id}%{base_sku}s{size_info}'
        
        entry = {
            "product_id": product_id,
            "sub_brand": None,
            "gender": gender,
            "age_group": get_age_group(mapped_gender),
            "age_range": get_age_range(mapped_gender),
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
            "sole_material": sole,
            "upper_material": upper,
            "closure_type": closure,
            "toe_type": toe,
            "heel_type":None,
            "weight": weight,
            "heel_to_toe_drop": heel_drop,
            "occasion": None,
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
                        print(f"Skipping {file} - not footwear or missing data")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-05'

    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    
    countries = ['INDIA']

    for country in countries:
        collection = db[f'crawler_sink_puma_{country.lower()}_footwear']
        print(f"Processing {country} footwear...")
        process_jsons(today_str, country, collection)
        print(f"Footwear data loading for {country} completed!")
    
    client.close()