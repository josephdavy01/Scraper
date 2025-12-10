import os
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

# Remapping genders
def remap_gender(gender):
    if gender in ['MAN', 'MEN']:
        return 'male'
    elif gender in ['WOMAN', 'WOMEN']:
        return 'female'
    else:
        return 'unisex'

# Get images
def get_images(imagelist, color):
    images = []
    for image in imagelist:
        if image.get('color') == color:
            temp = {
                "url": 'https:' + image['url'],
                "image_style": 's0'
            }
            images.append(temp)
    return images

# Function to create individual JSON objects for each SKU
def create_individual_json(fetch_date, json_data, gender):
    all_products = []
    product = json_data['product']
    variants = json_data['variants']
    imageslist = json_data['images']
    
    name = product['name'].lower()
    gender = remap_gender(gender)
    url = product['url']
    description = product.get('description')
    if not description:
        description = None

    for variant in variants:
        vname = variant['name'].split('-')[-1].strip()
        cname = vname.split('/')[0].strip()
        sizename = vname.split('/')[-1].strip()
        sku = variant['sku']
        pid = 'srb' + sku[:-4]
        cid = sku[-4:-2]
        price = float(variant['price']) / 100
        
        oldprice = float(variant['compare_at_price']) / 100 if variant['compare_at_price'] else price
        availability = 'in_stock' if variant['available'] else 'out_of_stock'
  
        composition = None
        origin = None
        images = get_images(imageslist, cname)

        entry = {
            "product_id": pid,
            "gender": gender,
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(fetch_date),
            "url": url,
            "title": name,
            "description": description,
            "product_ref_code": None,
            "color_id": f'{pid}%{cid}',
            "color_name": cname,
            "color_ref_code": None,
            "sku": f'{pid}%{sku}',
            "size_name": sizename,
            "size_ref_code": None,
            "price": price,
            "launch_price": oldprice,
            "availability": availability,
            "demand": None,
            "composition": composition,
            "origin": origin,
            "images": images
        }
        all_products.append(entry)
    return all_products

def shoe_type(data):
    keys = ["loafers", "sneakers"]
    title = data.get("name", "").lower()
    if any(key in title for key in keys):
        return True
    return False

# Function to log SKU details to CSV
def log_sku_details_to_csv(log_data, log_file):
    df = pd.DataFrame(log_data)
    df.to_csv(log_file, index=False)

def get_folders(sub_folders, exclude_folder=None):
    exclude_folder = exclude_folder or []  
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    return [folder for folder in folders if '.json' not in folder]

def process_jsons(fetch_date, country):
    log_data = []
    gender_folder = os.path.join(country, 'Data', fetch_date, 'Json_data')
    genders = get_folders(gender_folder, ['KIDS'])
    print(genders)
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, ['ties', 'cap', 'perfumes', 'belts', 'socks', 'wallets', 'shoes'])
        print(categories)
        for category in categories:
            file_folder = os.path.join(category_folder, category)
            files = os.listdir(file_folder)
            for file in files:
                file_path = os.path.join(file_folder, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as json_file:
                        data = json.load(json_file)
                    skus = create_individual_json(fetch_date, data, gender)
                    for sku in skus:
                        if not shoe_type(data):
                            print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                            collection.insert_one(sku)
                            log_data.append({"file_path": file_path, "sku": sku["sku"], "status": 'new'})
                except Exception as e:
                    print(file_path)
                    print(e)
                    traceback.print_exc()

    log_folder = os.path.join(country, 'Data', fetch_date, 'Validation')
    os.makedirs(log_folder, exist_ok=True)  
    log_file = os.path.join(log_folder, f'sku_log_{fetch_date}.csv')
    log_sku_details_to_csv(log_data, log_file)
    print(f'SKU log for {country} {fetch_date} is now saved')

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-08'
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = ['UAE']

    for country in countries:
        collection = db[f'crawler_sink_sacoor_brothers_{country.lower()}']
        process_jsons(today_str, country)

    client.close()
