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
    format_string_date_only = '%Y-%m-%d'
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            return datetime.strptime(date_string, format_string_date_only)
    
def remap_gender(json_data):
    gender_val = str(json_data.get('gender', '')).strip()
    gender_val = gender_val.split("'")[0].lower().strip()
    if gender_val == "women":
        return 'female'
    elif gender_val == "men":
        return 'male'
    elif gender_val == "big kids":
        return 'kids'
    else:
        return 'unisex'
    
def is_clothing(json_data):
    clothing_sizes = {"s", "m", "l", "xl", "xxl", "xxxl", "xs"}

    availibility = json_data.get("availibility", {})
    if not availibility:
        return False

    for size in availibility.keys():
        size_clean = size.strip().lower()
        if size_clean not in clothing_sizes:
            return False
    return True



def get_age_group(gender):
    if gender in ['female', 'male']:
        return ['adult']
    if gender == 'kids':
        return ['junior']
    return ['adult']

def get_age_range(gender):
    if gender in ['female', 'male']:
        return ['18y']
    if gender == 'kids':
        return ['2y', '8y']
    return ['18y']

def full_descriptions(json_data):
    descriptions = json_data.get("description", '')
    descriptions = re.sub(r"<.*?>", " ", descriptions)  
    descriptions = re.sub(r"[\r\n]+", " ", descriptions)  
    descriptions = re.sub(r"\s+", " ", descriptions).strip()
    return descriptions

def extract_prices(json_data):
    offers = json_data.get("offers", {})

    try:
        price = float(offers.get("price", None)) if offers.get("price") is not None else None
    except ValueError:
        price = None

    try:
        list_price = float(offers.get("listPrice", None)) if offers.get("listPrice") is not None else None
    except ValueError:
        list_price = None

    launch_price = list_price if list_price is not None else price

    return {
        "launch_price": launch_price,
        "price": price
    }

def get_image_style(image_list):
    images = []
    for image in image_list:
        temp = {
            "url": image,
            "image_style": 's0'
        }
        images.append(temp)

    if images:
        images[len(images) - 1]['image_style'] = 'n_f_f_C'
    return images 

def clean_product_name(name: str) -> str:
    if not name:
        return ""
    
    # Define patterns to remove (case insensitive)
    patterns = [
        r"^\s*all gender\s*",
        r"^\s*men's\s*",
        r"^\s*women's\s*",
        r"^\s*big kids\s*",
        r"^\s*little kids\s*"
    ]
    
    cleaned_name = name.strip()
    for p in patterns:
        cleaned_name = re.sub(p, "", cleaned_name, flags=re.IGNORECASE)

    return cleaned_name.strip()


def create_individual_json(today_str, json_data, gender):
    all_products=[]
    if not json_data or not isinstance(json_data, dict):
        return []
    
    if not is_clothing(json_data):
        return []
    product = json_data.get("product", {})


    raw_name = product.get('name', '')
    name = clean_product_name(raw_name).lower()
    url = json_data.get('url', '')     
    gender = remap_gender(json_data)
    product_id = 'hok' + product.get('productID', '')
    descriptions = full_descriptions(product)
    cid = json_data.get('color_id', '')
    raw_images = json_data.get('images', [])
    images = get_image_style(raw_images)
    key_features = json_data.get('features', [])
    if key_features:
        descriptions += '\n' + ' | '.join(key_features)
    prices = extract_prices(product)
    price = prices["price"]
    launch_price = prices["launch_price"]
    composition = json_data.get('composition','')
    if composition == '':
        composition = None
    occasion = json_data.get('occasion')
    if occasion:
        descriptions += '|' + occasion

    availibility = json_data.get("availibility", {})
    if not availibility:
        return []

    for size, status in availibility.items():
        size_name = size.strip()
        if not size_name:
            continue

        status_clean = status.strip().lower()

        if "low" in status_clean:
            availability = "low_stock"
        elif "in" in status_clean:
            availability = "in_stock"
        else:
            availability = "out_of_stock"

        size_specific_sku = f"{product_id}%p{product_id.replace('hok', '')}c{cid}s{size_name}"
        color_name = json_data.get('color_name', '').strip().lower()


        
        entry = {
            "product_id": product_id,
            "sub_brand": None,
            "gender": gender,
            "age_group": get_age_group(gender),
            "age_range": get_age_range(gender),
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": name,
            "description": descriptions,
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
            "composition" : composition,
            "origin": None,
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
                        print(f"Skipping {file} - not apparel or missing data")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()


if __name__ == "__main__":
    today_str =date.today().strftime('%Y-%m-%d')
    
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    
    countries = ['UK']
    
    for country in countries:
        collection = db[f'crawler_sink_hoka_{country.lower()}_apparel']
        print(f"Processing {country} apparel...")
        dates = os.listdir(f'{country}/Data')
        for today_str in dates:
            process_jsons( today_str, country, collection)
        
        print(f"Apparel data loading for {country} completed!")
    
    client.close()