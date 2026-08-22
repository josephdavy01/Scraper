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
    if 'unisex' in gender:
        return 'unisex'
    else:
        if gender in ['men', 'boys', 'mens', 'mens;']:
            return 'male'
        elif gender in ['women', 'girls', 'womens', 'womens;']:
            return 'female'
        else:
            return 'unisex'

# Get images
def get_images(media):
    images = []
    for i in range(0, len(media)):
        if media[i]['mediaContentType'] == 'IMAGE':
            url = media[i]['image']['url']
            temp = {
                "url": url,
                "image_style": 's0'
            }
            images.append(temp)
    
    return images

# Function to create individual JSON objects for each SKU
def create_individual_json(base_url, today_str, json_data, gender):
    all_products = []
    media = json_data['media']['results']

    images = get_images(media)

    name = json_data['title'].lower()
    url = base_url + json_data['handle']
    gender = remap_gender(gender.lower())
    description = json_data['description']
    pid = 'pag' + json_data['sku'].split('-')[0].strip()
    cname = json_data['color'].strip().lower()
    cid = json_data['sku'].split('-')[1].strip()
    color_ref = json_data['sku']

    composition = None
    for i in json_data['tags']:
        if 'styleContent:' in i:
            composition = i.split(':')[-1].replace('/', ',')

    for size in json_data['variants']['edges']:
        sname = size['title']
        sku = size['sku']
        price = float(size['price']['amount'])
        oldprice = float(size['compareAtPrice']['amount'])
        availableForSale = size['availableForSale']
        if availableForSale:
            availability = 'in_stock'
        else:
            availability = 'out_of_stock'

        entry = {
            "product_id": pid,
            "gender": gender,
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": name,
            "description": description,
            "product_ref_code" : None,
            "color_id": f'{pid}%{cid}',
            "color_name": cname,
            "color_ref_code" : color_ref,
            "sku": f'{pid}%{sku}',
            "size_name": sname,
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

def get_folders(sub_folders, exclude_folder = None):
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    # Filter out any folder that is in the exclude list
    return [folder for folder in folders if '.json' not in folder]

# In your process_jsons function
def process_jsons(base_url, today_str, country):
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = get_folders(gender_folder, [])
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, [])
        for category in categories:
            file_folder = os.path.join(category_folder, category)
            files = os.listdir(file_folder)
            for file in files:
                file_path = os.path.join(file_folder , file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    skus = create_individual_json(base_url, today_str, data, gender)
                    collection.insert_many(skus)
                    for sku in skus:
                        print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                except Exception as e:
                    print(file_path)
                    print(e)
                    traceback.print_exc()

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = "2025-12-06"

    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = {
        'USA' : 'https://paige.com/products/'
    }

    for country, base_url in countries.items():
        collection = db[f'crawler_sink_paige_{country.lower()}']
        # Process folder and log SKU details
        process_jsons(base_url, today_str, country)

    client.close()