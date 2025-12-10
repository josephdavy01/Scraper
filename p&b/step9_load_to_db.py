import os
import json
import pymongo
import traceback
import pandas as pd
from datetime import date, datetime

# Function to get the style of an image based on its filename
def get_image_style(image_urls):
    images = []
    for name, url in image_urls.items():
        filename = url.split('/')[-1].split('.')[0]
        image_style = 's0'

        if '3_1_0' not in filename:
            if 'a6m' in image_urls.keys() and 'a1m' in image_urls.keys():
                if name == 'a6m':
                    image_style = 'n_f_f_c'
                elif name == 'a1m':
                    image_style = 'm_f_f_c'
                elif '.mp4' in url:
                    image_style = 'video'
                
            temp = {
                "url": url,
                "image_style": image_style
            }
            images.append(temp)
    return images

# Function to get composition
def extract_composition_details(composition_detail):
    def extract_areas(areas):
        area_strs = []
        for area in areas:
            components_str = ', '.join([f"{comp['material']} {comp['percentage']}" for comp in area['components']])
            area_strs.append(f"{area['description']} : ({components_str})")
        return ', '.join(area_strs)

    def extract_components(components):
        return ', '.join([f"{comp['material']} {comp['percentage']}" for comp in components])

    parts_strs = []
    for part in composition_detail['parts']:
        if part['areas']:
            part_str = f"{part['description']} : ({extract_areas(part['areas'])})"
        else:
            part_str = f"{part['description']} : ({extract_components(part['components'])})"
        parts_strs.append(part_str)
    
    return ', '.join(parts_strs)

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

def get_image_urls(colorcode, xmedia):
    temp = {}
    for tempmedia in xmedia:
        if tempmedia['colorCode'] == colorcode:
            for j in tempmedia['xmediaItems']:
                for k in j['medias']:
                    extrainfo = k.get('extraInfo', '')
                    if extrainfo:
                        name = extrainfo.get('originalName', '')
                        url = extrainfo.get('deliveryUrl', '')
                        if name and url:
                            temp[name] = url
    if temp:
        return temp
    else:
        return {}

# Mapping of old to new availability values
def available_remap(avail):
    availability_map = {
        "SHOW": "in_stock",
        "BACK_SOON": "back_soon",
        "COMING_SOON": "coming_soon",
        "SOLD_OUT": "out_of_stock",
        "HIDDEN" : "out_of_stock",
        "RUNNING_OUT" : "low_on_stock" 
    }
    return availability_map[avail]

# Function to create individual JSON objects for each SKU
def create_individual_json(c_code, today_str, json_data):
    all_products = []
    name = json_data.get('nameEn', '').lower()
    pid = str(json_data.get('id', ''))
    gender = json_data.get('sectionNameEN', '')
    if gender == 'MEN':
        gender = 'male'
    elif gender == 'WOMEN' or gender == '':
        gender = 'female'
    else:
        gender = 'unisex'
    
    description = json_data['bundleProductSummaries'][0]['detail'].get('longDescription', None)
    if description == '':
        description = None
    reference = json_data['bundleProductSummaries'][0]['detail'].get('reference', '')
    apid = 'pnb' + reference.split('-')[0]
    
    colors = json_data['bundleProductSummaries'][0]['detail'].get('colors', [])
    xmedia = json_data['bundleProductSummaries'][0]['detail'].get('xmedia', [])
    for index, color in enumerate(colors):
        c_id = str(color.get('id', ''))
        c_reference = color.get('reference', None)
        c_name = color.get('name', '').lower().strip()
        url = f"https://www.pullandbear.com/{c_code}/{json_data['name'].lower().replace('-','').replace(' ','-')}-l{json_data['bundleProductSummaries'][0]['detail']['reference'].split('-')[0]}?cS={color['id']}&pelement={pid}"
        
        # Check if 'compositionDetail' exists before trying to access it
        composition = extract_composition_details(color['compositionDetail']) if 'compositionDetail' in color else ''
        if 'confection' in color['traceability'].keys():
            origin = ", ".join(color['traceability']['confection'].get('country', '')).lower()
        elif 'assembly' in color['traceability'].keys():
            origin = ", ".join(color['traceability']['assembly'].get('country', '')).lower()
        else:
            origin = None
        if origin == '':
            origin = None
        image_urls = get_image_urls(c_id, xmedia)
        if image_urls:
            images = get_image_style(image_urls)
        else:
            images = []
        
        for size in color.get('sizes', []):
            sku = str(size.get('sku', ''))
            sizename = size.get('name', '')
            sizereference = size.get('partnumber', '')
            price = float(size.get('price', 0) or 0) / 100
            if not price or price == 0:
                continue
            oldprice = float(size.get('oldPrice', 0) or 0) / 100
            if oldprice == 0 or oldprice == None:
                oldprice = price
            availability = available_remap(size.get('visibilityValue', ''))
            entry = {
                "product_id": apid,
                "gender": gender,
                "age_group": ['adult'],
                "age_range": ['18y'],
                "date_of_scraping": parse_launch_date(today_str),
                "url": url,
                "title": name,
                "description": description,
                "product_ref_code" : reference,
                "color_id": f'{apid}%{c_id}',
                "color_name": c_name,
                "color_ref_code" : c_reference,
                "sku": f'{apid}%{sku}',
                "size_name": sizename,
                "size_ref_code" : sizereference,
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

# Function to process a folder and log SKU details
def process_jsons(today_str, country, c_code):
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

                    product_type = str(data.get('productType', '')).strip().lower()
                    if product_type != 'clothing':
                        print(f" {product_type} not clothing so ,skipping!!!")
                        continue

                    skus = create_individual_json(c_code, today_str, data)
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
    # today_str='2025-11-05'

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

   # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    # Assign countries based on the day
    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = {
            'Australia' : 'au',
            'Saudi' : 'sa/en',
            'Spain' : 'es/en',
            'Turkey' : 'tr/en'
            }
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = {
            'UAE' : 'ae',
            'UK' : 'gb',
            'USA' : 'us'
            }
    else:
        countries = {}

    for country, code in countries.items():
        collection = db[f'crawler_sink_pull&bear_{country.lower()}']
        process_jsons(today_str, country, code)

    client.close()