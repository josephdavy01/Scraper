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
    format_string_with_ms_no_tz = '%Y-%m-%d %H:%M:%S.%f'
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            try:
                return datetime.strptime(date_string, format_string_date_only)
            except ValueError:
                return datetime.strptime(date_string, format_string_with_ms_no_tz)

# Function to get the style of an image based on its filename
def get_images(images):
    image_dict = {i: img for i, img in enumerate(images)}
    mi, ni = (0, len(image_dict) - 2) if len(image_dict) > 2 else (-1, len(image_dict) - 2 if len(image_dict) > 1 else -1)

    images = [
        {'url': img, 'image_style': 'm_f_f_c' if i == mi else 'n_f_f_c' if i == ni else 's0'}
        for i, img in image_dict.items()
    ]
    return images

def remap_gender(gender):
    gender = gender.strip().lower()
    male_terms = ["male", "m", "man", "boy", "gentleman", "men"]
    female_terms = ["female", "f", "woman", "girl", "lady", "women"]

    if gender in male_terms:
        return "male"
    elif gender in female_terms:
        return "female"
    else:
        return "unisex"

# Function to create individual JSON objects for each SKU
def create_individual_json(fetch_date, gender, data, filename):
    all_products = []
    product = data['product']
    prices = data['price']
    sizes = data['sizes']
    attributes = data['attributes']

    # Attributes
    composition_data = attributes.get('Composition')
    if composition_data:
        composition_list = json.loads(composition_data)
        composition = 'compositions: ' + ', '.join(composition_list)
    else:
        composition = None

    # Price
    if 'regularprice' in prices.keys():
        price = float(prices['specialprice'])
        if not price or price == 0:
            return
        oldprice = float(prices['regularprice'])
    else:
        price = float(prices['specialprice'])
        oldprice = price

    tpid = product['sku'][:-3]
    pid = 'hnm' + tpid
    name = product['name'].lower()
    gender = remap_gender(gender.lower())
    handle = filename.split('.')[0]
    url = f'https://sa.hm.com/en/{handle}'
    description = product['description']
    images = get_images(product['image'])

    # Color
    cname = data['color'].lower().strip()
    cid = product['sku'][-3:]

    for size, availability in sizes.items():
        sku = f'{tpid}{cid}s{size.lower()}'
        entry = {
            "product_id": pid,
            "gender": gender,
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(fetch_date),
            "url": url,
            "title": name,
            "description": description,
            "product_ref_code" : tpid,
            "color_id": f'{pid}%{cid}',
            "color_name": cname,
            "color_ref_code" : f'{tpid}{cid}',
            "sku": f'{pid}%{sku}',
            "size_name": size,
            "size_ref_code" : None,
            "price": price,
            "launch_price": oldprice,
            "availability": availability,
            "demand": None,
            "composition": composition,
            "origin": None,
            "images": images
        }
        all_products.append(entry)
    return all_products

# Function to get names of subfolders in a folder, excluding specified folders
def get_subfolder_names(folder_path, exclude_folders=None):
    exclude_folders = exclude_folders if exclude_folders else []
    return [f.name for f in os.scandir(folder_path) if f.is_dir() and f.name not in exclude_folders]

# Function to process a folder and log SKU details
def process_folder(root_path, fetch_date):
    log_data = []

    genders_path = os.path.join(root_path, "Json_data")
    genders = get_subfolder_names(genders_path, ['Kids', 'Baby'])
    
    for gender in genders:
        files_path = os.path.join(genders_path, gender)
        files = os.listdir(files_path)
        for file in files:
            file_path = os.path.join(files_path, file)
            print(file_path)
            with open(file_path, 'r') as json_file:
                data = json.load(json_file)
                try:
                    skus = create_individual_json(fetch_date, gender, data, file)
                    for sku in skus:
                        print(f'Inserting pid: {sku["product_id"]}, sku: {sku["sku"]}')
                        collection.insert_one(sku)
                        log_data.append({"file_path": file_path, "sku": sku["sku"], "status": 'new'})
                except Exception as e:
                    print(f"Error processing file: {file_path}: {e}")
                    traceback.print_exc()
            
if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = "2025-12-05"


    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = ['Saudi']
        
    for country in countries:
        collection = db[f'crawler_sink_h&m_{country.lower()}']
        root_path = rf"{country}/Data/{today_str}"
        # Process folder and log SKU details
        process_folder(root_path, today_str)

    client.close()