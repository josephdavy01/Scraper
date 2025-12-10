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
    if 'unisex' in gender or ('boys' in gender and 'girls' in gender):
        return 'unisex'
    elif 'boys' in gender:
        return 'male'
    elif 'girls' in gender:
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

def get_age_group(age_range):
    new_born_ages = ['0m', '1m', '2m', '3m', '4m', '5m', '6m']
    baby_ages = ['7m', '8m', '9m', '10m', '11m', '12m', '13m', '14m', '15m', '16m', '17m', '18m', '19m', '20m', '21m', '22m', '23m', '24m']
    junior_ages = ['2y', '3y', '4y', '5y', '6y', '7y']
    senior_ages = ['8y', '9y', '10y', '11y', '12y']
    teen_ages = ['13y', '14y', '15y', '16y', '17y']
    adult_ages = ['18y']

    age_goup_list = ['new_born', 'baby', 'junior', 'senior', 'teen', 'adult']

    if len(age_range) == 1:
        if age_range[0] in new_born_ages:
            return ['new_born']
        elif age_range[0] in baby_ages:
            return ['baby']
        elif age_range[0] in junior_ages:
            return ['junior']
        elif age_range[0] in senior_ages:
            return ['senior']
        elif age_range[0] in teen_ages:
            return ['teen']
        elif age_range[0] in adult_ages:
            return ['adult']
    else:
        age_group = []
        start = age_range[0]
        end = age_range[-1]

        if start in new_born_ages:
            sindex = age_goup_list.index('new_born')
        elif start in baby_ages:
            sindex = age_goup_list.index('baby')
        elif start in junior_ages:
            sindex = age_goup_list.index('junior')
        elif start in senior_ages:
            sindex = age_goup_list.index('senior')
        elif start in teen_ages:
            sindex = age_goup_list.index('teen')
        elif start in adult_ages:
            sindex = age_goup_list.index('adult')
        
        if end in new_born_ages:
            eindex = age_goup_list.index('new_born')
        elif end in baby_ages:
            eindex = age_goup_list.index('baby')
        elif end in junior_ages:
            eindex = age_goup_list.index('junior')
        elif end in senior_ages:
            eindex = age_goup_list.index('senior')
        elif end in teen_ages:
            eindex = age_goup_list.index('teen')
        elif end in adult_ages:
            eindex = age_goup_list.index('adult')

        for i in range(sindex, eindex + 1):
            age_group.append(age_goup_list[i])

        if age_group == []:
            age_group = ['others']
            
        return age_group

def remap_age_range(age_range):
    if age_range[1] == '2y':
        fi = int(float(age_range[0].replace('y', '')) * 12)
        si = int(float(age_range[1].replace('y', '')) * 12)
        return [str(fi) + 'm', str(si) + 'm']
    elif age_range[0] == '24m':
        fi = int(float(age_range[0].replace('m', '')) / 12)
        si = int(float(age_range[1].replace('m', '')) / 12)
        return [str(fi) + 'y', str(si) + 'y']
    return age_range

def get_age_range(size):
    if 'M' in size:
        tsize = size.replace('M', '')
        srange = tsize.split('-')
        age_range = [srange[0] + 'm', srange[1] + 'm']
        age_range = remap_age_range(age_range)
        return age_range
    elif 'Y' in size:
        tsize = size.replace('Y', '')
        srange = tsize.split('-')
        age_range = [srange[0] + 'y', srange[1] + 'y']
        age_range = remap_age_range(age_range)
        return age_range
    return None

# Function to create individual JSON objects for each SKU
def create_individual_json(base_url, today_str, json_data, category):
    all_products = []
    products= json_data['products']
    for product in products:
        name = product['name'].lower()
        pid = 'pmr' + product['productCode'][:-3]
        if 'boys' in category:
            gender = 'male'
        elif 'girls' in category:
            gender = 'female'
        else:
            gender = remap_gender(product['categorySpecific']['gender'].lower())

        url = base_url + product['slug']
        description = product['description']
        if description == '':
            description = None
        cid = product['colourCode']
        cname = product['displayColor'].lower().strip()
        composition = product['categorySpecific']['materialComposition']
        origin = product['displayCountryOrigin'].lower().strip()
        origin = origin.split(";")[0]
        
        if origin == '':
            origin = None
        images = get_images(product['images'])
        for size in product['variants']:
            sku = size['sku']
            sizename = size['displaySize'].strip()
            age_range = get_age_range(sizename)
            age_group = get_age_group(age_range)
            price = float(size['price'].split('$')[-1])
            oldprice = float(product['masterPrice'].split('$')[-1])
            if oldprice == 0 or oldprice == None:
                oldprice = price
            availability = 'in_stock'

            entry = {
                "product_id": pid,
                "gender": gender,
                "age_group": age_group,
                "age_range": age_range,
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
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    # Filter out any folder that is in the exclude list
    return [folder for folder in folders if '.json' not in folder]

# In your process_jsons function
def process_jsons(base_url, today_str, country):
    log_data = []
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = get_folders(gender_folder, ['men', 'women'])

    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, [
            'baby-boys_shoes', 'baby-girls_shoes',
            'newborn-baby_hats-&-mittens', 'boys_boys-shoes',
            'browse-by-product_shoes', 'girls_girls-shoes'
        ])

        for category in categories:
            file_folder = os.path.join(category_folder, category)
            files = os.listdir(file_folder)

            for file in files:
                file_path = os.path.join(file_folder, file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)

                    skus = create_individual_json(base_url, today_str, data, category)
                    fliter = data.get("category") == "Clothing"

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
                        logging.info(f"it's {fliter} — skipping {file}")

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
        collection = db[f'crawler_sink_primark_{country.lower()}_kids']
        # Process folder and log SKU details
        process_jsons(base_url, today_str, country)

    client.close()