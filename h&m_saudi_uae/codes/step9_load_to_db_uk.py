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
            
def get_availability(gender, tpid, avail_path):
    file_path = f'{avail_path}/{gender}/{tpid}.json'
    if os.path.exists(file_path):
        with open(file_path, 'r') as json_file:
            data = json.load(json_file)
        return data
    return None

# Function to get the style of an image based on its filename
def get_images(images_list):
    images = []
    for image in images_list:
        url = image['baseUrl']
        assettype = image['assetType']
        image_style = 's0'

        if assettype == 'DESCRIPTIVESTILLLIFE':
            image_style = 'n_f_f_c'
        elif assettype == 'LOOKBOOK':
            image_style = 'm_f_f_c'
            
        images.append({
            'url': url,
            'image_style': image_style
        })
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
    
def get_materialdetails(materialdetails):
    detaillist = []
    for material in materialdetails:
        name = material['name']
        description = material['description']
        detaillist.append(f'{name} : {description}')

    details = ', '.join(detaillist)
    return details

# Function to create individual JSON objects for each SKU
def create_individual_json(fetch_date, gender, product, avail_path):
    all_products = []
    tpid = product['productId']
    avail_dict = get_availability(gender, tpid, avail_path)

    pid = 'hnm' + tpid
    name = product['productName'].lower()
    gender = remap_gender(gender.lower())

    variants = product['variations']
    for vcode, variant in variants.items():
        url = 'https://www2.hm.com' + variant['url']
        cname = variant['name'].lower().strip()
        cid = vcode[-3:]
        description = variant['description']
        oldprice = float(variant['whitePriceValue'])
        price = float(variant.get('redPriceValue', oldprice))
        if not price or price == 0:
            continue
        compositions = ', '.join(variant['compositions'])
        materialdetail = get_materialdetails(variant.get('materialDetails', []))
        composition = f'compositions: {compositions} | materials: {materialdetail}'
        images = get_images(variant['images'])

        sizes = variant['sizes']
        for size in sizes:
            sname = size['name']
            sizecode = size['sizeCode']
            sku = f'{tpid}{cid}s{sname.lower()}'
            if avail_dict:
                if 'fewPieceLeft' in avail_dict.keys() and sizecode in avail_dict['fewPieceLeft']:
                    availability = 'low_on_stock'
                elif 'availability' in avail_dict.keys() and sizecode in avail_dict['availability']:
                    availability = 'in_stock'
                else:
                    availability = 'out_of_stock'
            else:
                availability = 'out_of_stock'

            entry = {
                "product_id": pid,
                "gender": gender,
                "age_group": ['adult'],
                "age_range": ['18y'],
                "date_of_scraping": parse_launch_date(fetch_date),
                "url": url,
                "title": name,
                "description": description,
                "product_ref_code" : vcode[:-3],
                "color_id": f'{pid}%{cid}',
                "color_name": cname,
                "color_ref_code" : vcode,
                "sku": f'{pid}%{sku}',
                "size_name": sname,
                "size_ref_code" : sku,
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
def process_folder(root_path, avail_path, fetch_date):
    log_data = []

    genders_path = os.path.join(root_path, "Json_data")
    genders = get_subfolder_names(genders_path, ['kids', 'baby'])
    
    for gender in genders:
        files_path = os.path.join(genders_path, gender)
        files = os.listdir(files_path)
        for file in files:
            file_path = os.path.join(files_path, file)
            print(file_path)
            with open(file_path, 'r') as json_file:
                data = json.load(json_file)
                try:
                    skus = create_individual_json(fetch_date, gender, data, avail_path)
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
    # today_str = '2025-08-28'

    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = ['UK']
        
    for country in countries:
        collection = db[f'crawler_sink_h&m_{country.lower()}']
        root_path = rf"{country}/Data/{today_str}"
        avail_path = rf"{country}/Data/{today_str}/Availability"
        # Process folder and log SKU details
        process_folder(root_path, avail_path, today_str)

    client.close()