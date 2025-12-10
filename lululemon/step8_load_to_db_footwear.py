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
    if gender in ['men', 'boys', 'mens', 'mens;']:
        return 'male'
    elif gender in ['women', 'girls', 'womens', 'womens;']:
        return 'female'
    else:
        return 'unisex'

# Get images
def get_images(ccode, productCarousel):
    for i in productCarousel:
        if i['color']['code'] == ccode:
            images = []
            for j in i['imageInfo']:
                temp = {
                    "url": j,
                    "image_style": 's0'
                }
                images.append(temp)
            return images

def get_description(ccode, colorAttributes):
    for i in colorAttributes:
        if i['colorId'] == ccode:
            description = i['wwmt']
            occasion = i['designedFor']['activityText'].lower().strip()
            weight = None
            heel_to_toe_drop = None
            attributes = i['featuresOrIngredients']['sections'][0]['attributes']
            attribute_text = []
            for j in attributes:
                text = j['text']
                attribute_text.append(text)

                if 'Heel-to-toe drop:' in text:
                    heel_to_toe_drop = text.split(':')[1].strip()

                if 'Weight:' in text:
                    weight = text.split(':')[1].split('(')[0].strip()

            description = description + '\n' + ' | '.join(attribute_text)
            return description, occasion, weight, heel_to_toe_drop

# Function to create individual JSON objects for each SKU
def create_individual_json(base_url, today_str, json_data, gender):
    all_products = []
    category = json_data['allLocalePids']['categoryUnifiedId']
    if category == 'shoes':
        gender = remap_gender(gender.lower())
        name = json_data['productSummary']['displayName'].lower()
        pid = 'lul' + json_data['productSummary']['productId'][4:]

        colorAttributes = json_data['colorAttributes']
        productCarousel = json_data['productCarousel']
        skus = json_data['skus']
        for i in skus:
            sku = i['id']
            size = i['size']
            oldprice = float(i['price']['listPrice'])
            if i['price']['salePrice']:
                price = float(i['price']['salePrice'])
                if not price or price == 0:
                    continue
            else:
                price = oldprice
            color = i['color']['name'].lower()
            colorcode = i['color']['code']
            colorreference = i['styleId']
            productreference = i['styleNumber']
            description, occasion, weight, heel_to_toe_drop = get_description(colorcode, colorAttributes)
            images = get_images(colorcode, productCarousel)
            if i['available']:
                availability = 'in_stock'
            else:
                availability = 'out_of_stock'
            url = f"{base_url}{i['skuUrl'].split('?')[0]}?color={colorcode}"
            
            entry = {
                "product_id": pid,
                "gender": gender,
                "age_group": ['adult'],
                "age_range": ['18y'],
                "date_of_scraping": parse_launch_date(today_str),
                "url": url,
                "title": name,
                "sub_brand": None,
                "description": description,
                "product_ref_code" : productreference,
                "color_id": f'{pid}%{colorcode}',
                "color_name": color,
                "color_ref_code" : colorreference,
                "sku": f'{pid}%{sku}',
                "size_name": size,
                "size_ref_code" : sku,
                "price": price,
                "launch_price": oldprice,
                "availability": availability,
                "sole_material": None,
                "upper_material": None,
                "occasion": occasion,
                "closure_type": None,
                "toe_shape": None,
                "heel_type": None,
                "weight": weight,
                "heel_to_toe_drop": heel_to_toe_drop,
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
def process_jsons(base_url, today_str, country, collection):
    gender_folder = os.path.join(country, today_str, 'Json_data')
    if os.path.exists(gender_folder):
        genders = get_folders(gender_folder, [])
        for gender in genders:
            category_folder = os.path.join(gender_folder, gender)
            categories = get_folders(category_folder, [])
            for category in categories:
                file_folder = os.path.join(category_folder, category)
                if os.path.exists(file_folder):
                    files = os.listdir(file_folder)
                    for file in files:
                        file_path = os.path.join(file_folder , file)
                        print(file_path)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as json_file:
                                data = json.load(json_file)
                            skus = create_individual_json(base_url, today_str, data, gender)
                            if skus:
                                collection.insert_many(skus)
                                for sku in skus:
                                    print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                        except Exception as e:
                            print(file_path)
                            print(e)
                            traceback.print_exc()

def footwear_load_to_db():
    # Get today's date
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-11-19'

    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = {
        'Canada' : 'https://shop.lululemon.com/en-ca',
        'USA' : 'https://shop.lululemon.com'
    }

    for country, base_url in countries.items():
        collection = db[f'crawler_sink_lululemon_{country.lower()}_footwear']
        # Process folder and log SKU details
        process_jsons(base_url, today_str, country, collection)
    client.close()

if __name__ == "__main__":
    footwear_load_to_db()