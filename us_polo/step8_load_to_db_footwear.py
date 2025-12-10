import logging
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
    if not gender:
        return 'unisex'
    gender = gender.lower().strip()
    if 'unisex' in gender:
        return 'unisex'
    elif gender in ['men', 'boys', 'mens', 'mens;']:
        return 'male'
    elif gender in ['women', 'girls', 'womens', 'womens;']:
        return 'female'
    else:
        return 'unisex'

def get_pid(pid):
    for i, j in pdict.items():
        if pid in j:
            return i
    return '0000000'

# Get images
def get_images(imagelist):
    images = []
    for image in imagelist:
        if image.get('src'):
            if image.get('position') == 1:
                temp = {
                    "url": 'https:' + image['src'],
                    "image_style": 'm_f_f_c'
                }
            else:
                temp = {
                    "url": 'https:' + image['src'],
                    "image_style": 's0'
                }
            images.append(temp)
    return images

# Function to create individual JSON objects for each SKU
def create_individual_json(base_url, fetch_date, json_data, gender):
    all_products = []
    product = json_data.get('product', {})
    descriptions = json_data.get('descriptions', {})
    description = descriptions.get('description', '').strip() 
    origin = descriptions.get('origin')
    name = product.get('title', '').lower()
    handle = product.get('handle', '')
    pid = 'usp' + get_pid(handle)
    cid = handle.split('-')[-1] if '-' in handle else handle
    gender = remap_gender(gender)
    url = base_url + handle
    images = get_images(product.get('media', []))
    for size in product.get('variants', []):
        cname = size.get('option3', '').strip().lower()
        sku = size.get('sku', '')
        sizename = size.get('option1', '')
        price = float(size.get('price', 0)) / 100
        if not price or price == 0:
            continue
        oldprice = float(size.get('compare_at_price', 0)) / 100
        stock = size.get('available', False)
        availability = 'in_stock' if stock else 'out_of_stock'
        entry = {
            "product_id": pid,
            "gender": gender,  
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(fetch_date),
            "url": url,
            "title": name,
            "sub_brand": None,
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
            "sole_material": None,
            "upper_material": None,
            "occasion": None,
            "shoe_type": None, 
            "closure_type": None,
            "toe_shape": None,
            "heel_type": None,
            "weight": None,
            "heel_to_toe_drop": None,
            "origin": origin,
            "images": images
        }
        all_products.append(entry)
    
    return all_products   

# Function to log SKU details to CSV
def log_sku_details_to_csv(log_data, log_file):
    df = pd.DataFrame(log_data)
    df.to_csv(log_file, index=False)

def get_folders(sub_folders, exclude_folder=None):
    if not os.path.exists(sub_folders):
        return []
    folders = os.listdir(sub_folders)
    exclude_folder = exclude_folder or []
    folders = [folder for folder in folders if folder not in exclude_folder]
    return [folder for folder in folders if not folder.endswith('.json')]  #

keys = ["Belly shoes", "Boots", "Derbies", "Flats", "Flip flops", "Loafers", "Sandals", "Shoes", "Slip-on shoes", "Slippers", "Sneakers"]

# Main processing function
def process_jsons(base_url, fetch_date,country):
    log_data = []
    gender_folder = os.path.join(country, 'Data', fetch_date, 'Json_data')
    genders = get_folders(gender_folder, ['KIDS'])
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, [])
        print(categories)
        for category in categories:
            file_folder = os.path.join(category_folder, category)
            if not os.path.exists(file_folder):
                continue
            files = os.listdir(file_folder)
            for file in files:
                file_path = os.path.join(file_folder, file)
                if not file.endswith('.json'):
                    continue
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    skus = create_individual_json(base_url, fetch_date, data, gender)
                    category =  data.get('product').get("type")
                    if category in keys:
                        for sku in skus:
                            print(f'Category:{category},Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                            collection.insert_one(sku)
                            log_data.append({"file_path": file_path, "sku": sku["sku"], "status": 'new'})
                    else:
                        logging.info("not a footwear{category}")
                except Exception as e:
                    print(file_path)
                    print(e)
                    traceback.print_exc()

    log_dir = os.path.join(country, 'Data', fetch_date, 'Validation')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'sku_log_{fetch_date}.csv')
    log_sku_details_to_csv(log_data, log_file)
    print(f'SKU log for {country} {fetch_date} is now saved')

if __name__ == "__main__":
    today = date.today()
    fetch_date = today.strftime('%Y-%m-%d')
    # fetch_date = '2025-12-06'

    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = {
        'India': 'https://uspoloassn.in/products/'
    }

    pid_path = 'us_polo_pid_remapping.json'

    if os.path.exists(pid_path):
        with open(pid_path, 'r') as json_file:
            pdict = json.load(json_file)
    else:
        pdict = {}

    for country, base_url in countries.items():
        collection = db[f'crawler_sink_uspolo_{country.lower()}_footwear']
        process_jsons(base_url, fetch_date,country)

    client.close()
