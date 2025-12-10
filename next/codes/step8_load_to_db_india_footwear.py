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
    if gender in ['Men']:
        return 'male'
    elif gender in ['Women']:
        return 'female'
    else:
        return 'unisex'

# Get images
def get_images(imagelist):
    images = []
    for image in imagelist:
        url = f"https://xcdn.next.co.uk{image['imageUrl']}"
        if image['shotType'] == 'SIP Still Life' and image['imageType'] == 'M':
            image_style = 'n_f_f_c'
        elif image['shotType'] == 'SIP Still Life' and image['imageType'] == 'B':
            image_style = 'n_b_f_c'
        else:
            image_style = 's0'
                
        temp = {
            "url": url,
            "image_style": image_style
        }
        images.append(temp)
    return images

# Function to create individual JSON objects for each SKU
def create_individual_json(today_str, product, gender):
    all_products = []
    name = product['title'].lower()
    pid = product['styleNumber']
    mpid = 'nxt' + pid
    cid = product['itemNumber']
    gender = remap_gender(gender)
    url = f"https://www.nextdirect.com/in/en/style/{pid}/{cid}"
    reference = product['productCode']
    description = product['itemDescription'].get('toneOfVoiceSanitised', None)
    cname = product['colour'].lower().strip()
    composition = product['itemDescription'].get('composition', None)
    origin = product['itemDescription'].get('countryOfOrigin', None)
    images = get_images(product['itemMedia'])

    for size in product['options']['options']:
        sizeid = size['value']
        sku = 'p' + pid + 'c' + cid + 's' + sizeid
        sizename = size['name'].strip()
        if size['stockStatus'] == 'InStock':
            availability = 'in_stock'
        elif size['stockStatus'] == 'SoldOut':
            availability = 'out_of_stock'
        else:
            availability = 'out_of_stock'

        if product['priceData']['wasPrice'] == None:
            price = float(size['priceUnformatted'])
            # logging.info(logging.info)
            oldprice = price
        else:
            price = float(size['priceUnformatted'])
            oldmin = product['priceData']['price']['minPrice']
            oldmax = product['priceData']['price']['maxPrice']
            newmin = product['priceData']['salePrice']['minPrice']
            newmax = product['priceData']['salePrice']['maxPrice']
            dis_percentage = int(((((oldmax - newmax)/oldmax) + ((oldmin - newmin)/oldmin))/2) * 100)
            oldprice = float(round(price/(100-dis_percentage)*100))
        entry = {
            "product_id": mpid,
            "gender": gender,
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": name,
            "description": description,
            "product_ref_code" : reference,
            "color_id": f'{mpid}%{cid}',
            "color_name": cname,
            "color_ref_code" : None,
            "sku": f'{mpid}%{sku}',
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


keys = [
    "Boots", "Sandals", "Shoes", "Slippers", "Trainers", "Wellies", "Swim Shoes"
]

def get_folders(sub_folders, exclude_folder = None):
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    # Filter out any folder that is in the exclude list
    return [folder for folder in folders if '.json' not in folder]

# In your process_jsons function
def process_jsons(today_str, country):
    log_data = []
    gender_folder = os.path.join(country,  today_str, 'Json_data')
    genders = genders = ["Men","Women","Women Dresses","Women Lingerie","Men Suits","Men Nightwear","Men Underwear","Women Workwear","Women Swimwear"]
    for gender in genders:
        file_folder = os.path.join(gender_folder, gender)
        files = os.listdir(file_folder)
        for file in files:
            file_path = os.path.join(file_folder , file)
            try:
                with open(file_path, 'r', encoding='utf-8') as json_file:
                    data = json.load(json_file)
                skus = create_individual_json(today_str, data, gender)
                category = data.get("category")
                if category in keys:
                    for sku in skus:
                        logging.info(f'Category:{category},Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                        collection.insert_one(sku)
                        log_data.append({"file_path": file_path, "sku": sku["sku"], "status": 'new'})
                else:
                    logging.info(f"Skpping the {category}")
            except Exception as e:
                logging.info(file_path)
                logging.info(e)

if __name__ == "__main__":
    countries = ['India']

    # Database connection
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-06'
    # Database connection
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    for country in countries:      
        collection = db[f'crawler_sink_next_{country.lower()}_footwear']
        process_jsons(today_str,country)

    client.close()
