import os
import json
import pymongo
import traceback
import logging
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
def get_images(imagelist):
    images = []
    for image in imagelist:
        url = image['url']
        if 'Model Full Length' in image['label']:
            image_style = 'm_f_f_c'
        elif 'Model Front View' in image['label']:
            image_style = 'm_f_h_c'
        elif 'Model Back View' in image['label']:
            image_style = 'm_b_h_c'
        elif 'Still Life Front View' in image['label']:
            image_style = 'n_f_f_c'
        else:
            image_style = 's0'
            
        temp = {
            "url": url,
            "image_style": image_style
        }
        images.append(temp)
    return images

# Function to create individual JSON objects for each SKU
def create_individual_json(base_url, today_str, json_data, gender):
    all_products = []
    products= json_data['products']
    for product in products:
        name = product['name'].lower()
        pid = 'pmr' + product['productCode'][:-3]
        gender = remap_gender(gender.lower())

        url = base_url + product['slug']
        description = product['description']
        if description == '':
            description = None
        cid = product['colourCode']
        cname = product['displayColor'].lower().strip()
        composition = product['categorySpecific']['body']
        origin = product['displayCountryOrigin'].lower().strip()
        origin = origin.split(";")[0]
        
        if origin == '':
            origin = None
        images = get_images(product['images'])
        for size in product['variants']:
            sku = size['sku']
            sizename = size['displaySize'].strip()
            price = float(size['price'].split('$')[-1])
            oldprice = float(product['masterPrice'].split('$')[-1])
            if oldprice == 0 or oldprice == None:
                oldprice = price
            availability = 'in_stock'

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

def get_folders(sub_folders, exclude_folder = None):
    if exclude_folder is None:
        exclude_folder = []
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    # Filter out any folder that is in the exclude list
    return [folder for folder in folders if '.json' not in folder]

# In your process_jsons function
def process_jsons(base_url, today_str, country, collection):
    log_data = []
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = get_folders(gender_folder, ['kids', 'baby'])

    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, [
            'slippers', 'socks', 'socks-&-tights', 'future-projects',
            'boots', 'loafers-&-brogues', 'sandals-&-sliders',
            'flip-flops-&-sliders', 'flats', 'heels', 'joggers',
            'sandals', 'trainers'
        ])

        for category in categories:
            file_folder = os.path.join(category_folder, category)
            files = os.listdir(file_folder)

            for file in files:
                file_path = os.path.join(file_folder, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)

                    skus = create_individual_json(base_url, today_str, data, gender)
                    fliter = data.get("category") == "Shoes"

                    if fliter:
                        for sku in skus:
                            print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                            collection.insert_one(sku)
                            log_data.append({
                                "file_path": file_path,
                                "sku": sku["sku"],
                                "status": 'new'
                            })
                    else:
                        logging.info(f"Skipping non-clothing file: {category}/{file}")

                except Exception as e:
                    print(file_path)
                    print(e)
                    traceback.print_exc()

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-06'

    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = {
        'USA' : 'https://www.primark.com/en-us/p/'
    }

    for country, base_url in countries.items():
        collection = db[f'crawler_sink_primark_{country.lower()}_footwear']
        # Process folder and log SKU details
        process_jsons(base_url, today_str, country, collection)

    client.close()