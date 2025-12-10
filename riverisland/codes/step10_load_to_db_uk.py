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
    if gender in ['Men', 'Boys', 'mens', 'mens;']:
        return 'male'
    elif gender in ['Women', 'Girls', 'womens', 'womens;']:
        return 'female'
    elif gender in ['boys', 'girls','kids']:
        return 'kids'
    else:
        return 'unisex'

# Get images
def get_images(imagelist):
    images = []
    for image in imagelist:
        if image['__typename'] == 'Image':
            url = image['url']
            if image['type'] == 'Main':
                image_style = 'm_f_f_c'
            elif image['type'] == 'Alt3':
                image_style = 'n_f_f_c'
            else:
                image_style = 's0'
                    
            temp = {
                "url": url,
                "image_style": image_style
            }
            images.append(temp)
    return images

def get_pid(pid):
    for i, j in pdict.items():
        if pid in j:
            return i
    return '0000000'

# Function to create individual JSON objects for each SKU
def create_individual_json(fetch_date, product, gender):
    all_products = []
    name = product['displayName'].lower()
    reference = product['productId']
    gender = remap_gender(gender)
    url = f"https://www.riverisland.com/p/{product['urlFriendlyName']}-{reference}"
    pid = 'rrd' + get_pid(reference)
    description = product['description'].replace('\n', '. ')
    cname = product['colour'].lower().strip()
    cid = cdict[cname]
    composition = ', '.join(product['materialCompositionInfo'])
    origin = None
    images = get_images(product['images'])

    for size in product['variants']:
        sizeid = size['id']
        sku = f'p{pid.replace('rrd','')}c{cid}s{sizeid}'
        
        sizename = size['dimensions'][0]['value'].strip()
        stock = int(size['inventoryQuantity'])
        if stock == 0:
            availability = 'out_of_stock'
        elif stock < 10:
            availability = 'low_on_stock'
        else:
            availability = 'in_stock'
        pricedata = size['priceInfo']['prices']

        if len(pricedata) == 1:
            price = float(pricedata[0]['formattedValue'].replace('£', ''))
            oldprice = price
        else:
            price = float(pricedata[0]['formattedValue'].replace('£', ''))
            oldprice = float(pricedata[1]['formattedValue'].replace('£', ''))
        
        if oldprice == 0 or oldprice == None:
            oldprice = price

        entry = {
            "product_id": pid,
            "gender": gender,
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(fetch_date),
            "url": url,
            "title": name,
            "description": description,
            "product_ref_code" : reference,
            "color_id": f'{pid}%{cid}',
            "color_name": cname,
            "color_ref_code" : None,
            "sku": f'{pid}%{sku}',
            "size_name": sizename,
            "size_ref_code" : None,
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

# Function to log SKU details to CSV
def log_sku_details_to_csv(log_data, log_file):
    df = pd.DataFrame(log_data)
    df.to_csv(log_file, index=False)

def get_folders(sub_folders, exclude_folder = None):
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    # Filter out any folder that is in the exclude list
    return [folder for folder in folders if '.json' not in folder]

# In your process_jsons function
def process_jsons(fetch_date, country):
    log_data = []
    gender_folder = os.path.join(country, 'Data', fetch_date, 'Json_data')
    genders = get_folders(gender_folder, ['Kids'])
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, ['coats-&-jackets', 'co-ord-sets', 'jeans'])
        for category in categories:
            file_folder = os.path.join(category_folder, category)
            files = os.listdir(file_folder)
            for file in files:
                file_path = os.path.join(file_folder , file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    skus = create_individual_json(fetch_date, data, gender)
                    for sku in skus:
                        print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                        collection.insert_one(sku)
                        log_data.append({"file_path": file_path, "sku": sku["sku"], "status": 'new'})
                except Exception as e:
                    print(file_path)
                    print(e)
                    traceback.print_exc()

    log_file = os.path.join(country, 'Data', fetch_date, 'Validation', f'sku_log_{fetch_date}.csv')
    log_sku_details_to_csv(log_data, log_file)
    print(f'SKU log for {country} {fetch_date} is now saved')

if __name__ == "__main__":
    today = date.today()
    fetch_date = today.strftime('%Y-%m-%d')
    # fetch_date = '2025-12-06'
    countries = ['UK']

    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    pid_path = 'riverisland_pid_remapping.json'
    cid_path = 'riverisland_cid_remapping.json'

    if os.path.exists(pid_path):
        with open(pid_path, 'r') as json_file:
            pdict = json.load(json_file)
    else:
        pdict = {}

    if os.path.exists(cid_path):
        with open(cid_path, 'r') as json_file:
            cdict = json.load(json_file)
    else:
        cdict = {}

    for country in countries:
        collection = db[f'crawler_sink_riverisland_{country.lower()}']
        # Process folder and log SKU details
        process_jsons(fetch_date, country)

    client.close()