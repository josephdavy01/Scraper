import os
import re
import json
import pymongo
import traceback
from datetime import date, datetime

EXCLUDED_KEYWORDS = [
    "toy", "cap", "sock", "footsie", "backpack", "scarf", "beanie",
    "glove", "mitten", "umbrella", "bag", "hat", "belt",
    "sneaker", "shoe", "boot"
]

EXCLUDE_SIZES = {"M/L", "PINK", "S/M", "UK1-5 (20-24cm)", "UK9-1(16-20cm)"}

def clean_composition(composition):
    new_composition = composition
    if 'Delivery Date' in composition or 'Gentle Machine' in composition:
        return None
    if 'CAUTION' in new_composition:
        new_composition = new_composition.split('CAUTION')[0].strip()
    if 'Imported' in new_composition:
        new_composition = new_composition.replace('Imported', '')
    if '<br>' in new_composition:
        new_composition = new_composition.replace('<br>', '')
    if '/ Exclusive of Decoration' in new_composition:
        new_composition = new_composition.replace('/ Exclusive of Decoration', '')
    if ', Exclusive of Decoration' in new_composition:
        new_composition = new_composition.replace(', Exclusive of Decoration', '')
    if 'time.' in new_composition:
        new_composition = new_composition.split('time.')[-1].strip()
    if ']' in new_composition:
        new_composition = new_composition.split(']')[-1].split('[')[0].strip()
    if ':' in new_composition:
        fisrt_part = new_composition.split(':')[0].strip().split(' ')[-1]
        if fisrt_part.isdigit():
            new_composition = new_composition.split(':')[-1]
            if ':' in new_composition:
                new_composition = new_composition.split(':')[0][:-6]
 
    if 'Base:' in new_composition:
        new_composition = 'Base: ' + new_composition.split('Base:')[-1].split('/')[0].strip()
    elif 'Body:' in new_composition:
        new_composition = 'Body: ' + new_composition.split('Body:')[-1].split('/')[0].strip()
    elif 'Shell:' in new_composition:
        new_composition = 'Shell: ' + new_composition.split('Shell:')[-1].split('/')[0].strip()
   
    return new_composition

with open("remapped_size.json", "r", encoding="utf-8") as f:
    SIZE_REMAPPING = json.load(f)

def is_excluded_product(title: str) -> bool:
    if not title:
        return False
    title_lower = title.lower()
    for word in EXCLUDED_KEYWORDS:
        pattern = r'\b' + re.escape(word) + r's?\b'
        if re.search(pattern, title_lower):
            return True
    return False

def parse_launch_date(date_string):
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    return datetime.now()

def detect_gender_from_title(title):
    title = title.lower()
    if re.search(r"\bboys?\b", title):
        return "male"
    elif re.search(r"\bgirls?\b", title):
        return "female"
    else:
        return "unisex"

def clean_product_id(raw_id: str) -> str:
    if not raw_id:
        return ''
    match = re.match(r"[A-Za-z]*([0-9]+)", raw_id)
    return match.group(1) if match else raw_id

def clean_and_combine_description(json_data):
    cleaned_desc = ""   

    desc = json_data.get("description", "")
    if desc:
        desc_parts = [part.strip(" -") for part in desc.split(".") if part.strip()]
        cleaned_desc = ". ".join(desc_parts)

    features = json_data.get("features", [])
    if features:
        features_str = " | ".join([f.strip(" -") for f in features])
        if cleaned_desc:
            cleaned_desc += " | " + features_str
        else:
            cleaned_desc = features_str

    return cleaned_desc

def get_images(json_data, cid):
    images = []
    main_images = json_data.get("images", {}).get("main", [])
    sub_images = json_data.get("images", {}).get("sub", [])
    for m in main_images:
        if m.get("colorCode") == cid:
            images.append({"url": m.get("url"), "image_style": "s0"})
            break
    for s in sub_images:
        images.append({"url": s.get("url"), "image_style": "s0"})
    return images

def extract_prices(json_data):
    def safe_get(price_obj):
        if isinstance(price_obj, dict):
            return price_obj.get("value")
        elif isinstance(price_obj, (int, float)):
            return price_obj
        elif isinstance(price_obj, str):
            num = re.findall(r"\d+\.?\d*", price_obj)
            return float(num[0]) if num else None
        return None
    return {
        "price": safe_get(json_data.get("prices", {}).get("price", json_data.get("price"))),
        "launch_price": safe_get(json_data.get("prices", {}).get("launch_price", json_data.get("launch_price"))),
    }

def get_age_group(age_range):
    new_born_ages = ['0m','1m','2m','3m','4m','5m','6m']
    baby_ages = ['7m','8m','9m','10m','11m','12m','13m','14m','15m','16m','17m','18m','19m','20m','21m','22m','23m','24m']
    junior_ages = ['2y','3y','4y','5y','6y','7y']
    senior_ages = ['8y','9y','10y','11y','12y']
    teen_ages = ['13y','14y','15y','16y','17y']
    adult_ages = ['18y']
    age_group_list = ['new_born','baby','junior','senior','teen','adult']
    if not age_range:
        return ['others']
    start, end = age_range[0], age_range[-1]
    def get_index(val):
        if val in new_born_ages: return age_group_list.index('new_born')
        if val in baby_ages: return age_group_list.index('baby')
        if val in junior_ages: return age_group_list.index('junior')
        if val in senior_ages: return age_group_list.index('senior')
        if val in teen_ages: return age_group_list.index('teen')
        if val in adult_ages: return age_group_list.index('adult')
        return -1
    sindex, eindex = get_index(start), get_index(end)
    if sindex == -1 or eindex == -1:
        return ['others']
    return age_group_list[sindex:eindex+1]

def map_age_group_from_size(size_name: str):
    if not size_name or size_name in EXCLUDE_SIZES:
        return None, []
    s = size_name.strip()
    s_norm = s.replace("–", "-").replace("—", "-")
    before_paren = s_norm.split("(", 1)[0].strip().lower() 
    bracket_part = None
    m = re.search(r"\(([^)]+)\)", s_norm)
    if m:
        bracket_part = m.group(1).strip().lower()
    else:
        digits = "".join(re.findall(r"\d+", s_norm))
        bracket_part = digits if digits else None
    mapped_labels = None
    if bracket_part and bracket_part in SIZE_REMAPPING:
        mapped_labels = SIZE_REMAPPING[bracket_part]
    else:
        if bracket_part:
            digits_only = "".join(re.findall(r"\d+", bracket_part))
            if digits_only and digits_only in SIZE_REMAPPING:
                mapped_labels = SIZE_REMAPPING[digits_only]
    if not mapped_labels:
        return None, []
    b = before_paren.lower()
    b = re.sub(r'\s+', ' ', b) 
    range_patterns = [
        r'age\s*(\d{1,2})\s*[-]\s*(\d{1,2})([ym])?',   # Age 3-4 or Age3-4 or Age 3-4y
        r'(\d{1,2})\s*[-]\s*(\d{1,2})([ym])\b',         # 3-4y or 3-4m
        r'\b(\d{1,2})\s*[-]\s*(\d{1,2})\b'              # 3-4 (no unit)
    ]
    start_age = end_age = None
    unit_hint = None 
    for pat in range_patterns:
        rm = re.search(pat, b, flags=re.IGNORECASE)
        if rm:
            start_age = int(rm.group(1))
            end_age = int(rm.group(2))
            if len(rm.groups()) >= 3 and rm.group(3):
                unit_hint = rm.group(3).lower()
            break
    if start_age is None:
        single_patterns = [
            r'age\s*(\d{1,2})([ym])?\b',   # age 3, age3y, age 6m
            r'\b(\d{1,2})([ym])\b'         # 3y or 6m (with unit)
        ]
        for pat in single_patterns:
            sm = re.search(pat, b, flags=re.IGNORECASE)
            if sm:
                start_age = int(sm.group(1))
                if len(sm.groups()) >= 2 and sm.group(2):
                    unit_hint = sm.group(2).lower()
                end_age = None
                break
    filtered = None
    if start_age is not None:
        if unit_hint:
            use_unit = unit_hint
        else:
            use_unit = 'm' if any('m' in lbl for lbl in mapped_labels) else 'y'
        if end_age is not None:
            allowed = {f"{i}{use_unit}" for i in range(start_age, end_age + 1)}
        else:
            allowed = {f"{start_age}{use_unit}"}
        filtered = [lbl for lbl in mapped_labels if lbl in allowed]
        if not filtered:
            alt_unit = 'y' if use_unit == 'm' else 'm'
            alt_allowed = {f"{i}{alt_unit}" for i in (range(start_age, (end_age or start_age) + 1))}
            filtered = [lbl for lbl in mapped_labels if lbl in alt_allowed]
        if filtered:
            age_range = filtered
        else:
            age_range = mapped_labels
    else:
        age_range = mapped_labels
    age_group = get_age_group(age_range)
    return age_group, age_range

def create_individual_json(today_str, json_data):
    all_products = []
    if not json_data or not isinstance(json_data, dict):
        return []
    json_gender = str(json_data.get('gender', '')).lower()
    if json_gender not in ["baby", "kids"]:
        print(f"Skipping product {json_data.get('product_id')} - gender not baby/kids ({json_gender})")
        return []
    title = str(json_data.get('title', '')).strip()
    gender = detect_gender_from_title(title)
    prdt_id = clean_product_id(json_data.get('product_id', ''))
    product_id = 'uni' + prdt_id
    if is_excluded_product(title):
        print(f"Skipping product {json_data.get('product_id')} - excluded ({title})")
        return []
    url = json_data.get('variant_url', '')
    descriptions = clean_and_combine_description(json_data)
    cid = json_data.get('color_id', '').replace("COL", "")
    color_name =json_data.get('color_name', '').strip().lower()
    images = get_images(json_data, cid)
    prices = extract_prices(json_data)
    origin_val = None
    composition = json_data.get("composition")
    if composition:
        cleaned_composition = clean_composition(composition)
    origin_raw = json_data.get("origin", None)
    if origin_raw:
        origin_val = origin_raw.split(",")[0].strip().lower()
    sizes = json_data.get("sizes", [])
    if not sizes:
        return []
    for size_obj in sizes:
        size_name = size_obj.get("size_name", "").strip()
        if not size_name or size_name in EXCLUDE_SIZES:
            continue
        availability = size_obj.get("availability", "").lower()
        size_id = size_obj.get("size_id")
        size_specific_sku = f"{product_id}%p{prdt_id}c{cid}s{size_id}"
        age_group, age_range = map_age_group_from_size(size_name)
        if prices["price"] is None:
            print(f"Skipping {product_id} size {size_name} - price is null")
            continue
        entry = {
            "product_id": product_id,
            "gender": gender,
            "age_group": age_group,
            "age_range": age_range,
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": title.lower(),
            "description": descriptions,
            "product_ref_code": None,
            "color_id": f'{product_id}%{cid}',
            "color_name": color_name,
            "color_ref_code": cid,
            "sku": size_specific_sku,
            "size_name": size_name, 
            "size_ref_code": size_id,
            "price": prices["price"],
            "launch_price": prices["launch_price"],
            "availability": availability,
            "demand": None,
            "origin": origin_val,
            "composition": cleaned_composition,
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
                            print(f'Product_id: {sku["product_id"]}, SKU: {sku["sku"]}, '
                                  f'AgeGroup: {sku["age_group"]}, AgeRange: {sku["age_range"]}')
                    else:
                        print(f"Skipping {file_name} - not kids or no valid sizes")
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client['tg_analytics']
    countries = ['India']
    for country in countries:
        collection = db[f'crawler_sink_uniqlo_{country.lower()}_kids']
        print(f"\nProcessing {country} kids apparel...")
        process_jsons(today_str, country, collection)
        print(f"Kids apparel data loading for {country} completed!")
    client.close()
