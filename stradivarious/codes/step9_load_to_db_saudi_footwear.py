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
        if '-r' not in filename:
            if ('c' in image_urls.keys() or 'c1' in image_urls.keys()) and 's1' in image_urls.keys():
                if name in ['c', 'c1']:
                    image_style = 'm_f_f_c'
                elif name == 's1':
                    image_style = 'n_f_f_c'
                elif name == 's2':
                    image_style = 'n_b_f_c'
                elif '.mp4' in url:
                    image_style = 'video'
                
            temp = {
                "url": url,
                "image_style": image_style
            }
            images.append(temp)
    return images

def extract_composition_details(composition_detail):
    def format_comps(components):
        return ', '.join(f"{c.get('material', '')} {c.get('percentage', '')}" for c in components)

    # Prepare default values
    upper = lining = sole = insole = ''
    if not composition_detail or 'parts' not in composition_detail:
        return upper, lining, sole, insole

    for part in composition_detail['parts']:
        desc = part.get('description', '').upper()
        value = ''
        if part.get('areas'):
            for area in part['areas']:
                if 'components' in area:
                    value = format_comps(area['components'])
        elif part.get('components'):
            value = format_comps(part['components'])

        if desc == 'UPPER':
            upper = value
        elif desc == 'LINING':
            lining = value
        elif desc == 'SOLE':
            sole = value
        elif desc == 'INSOLE':
            insole = value

    return upper, lining, sole, insole

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
    
def available_remap(avail):
    # Mapping of old to new availability values
    availability_map = {
        "SHOW": "in_stock",
        "BACK_SOON": "back_soon",
        "COMING_SOON": "coming_soon",
        "SOLD_OUT": "out_of_stock",
        "RUNNING_OUT": "low_on_stock"
        }
    return availability_map[avail]
    
# Function to create individual JSON objects for each SKU
def create_individual_json(c_code, fetch_date, json_data):
    all_products = []
    product_type = json_data.get('productType').lower().strip()
    
    name = json_data.get('nameEn', '').lower()
    pid = str(json_data.get('id', ''))
    gender = json_data.get('sectionNameEN', '')
    if gender == 'MEN':
        gender = 'male'
    elif gender == 'WOMEN':
        gender = 'female'
    else:
        gender = 'unisex'
        
    description = json_data['bundleProductSummaries'][0]['detail'].get('longDescription', '')
    if description == '':
        description = None
    reference = json_data['bundleProductSummaries'][0]['detail'].get('reference', '')
    apid = 'str' + reference.split('-')[0]
    
    colors = json_data['bundleProductSummaries'][0]['detail'].get('colors', [])
    xmedia = json_data['bundleProductSummaries'][0]['detail'].get('xmedia', [])
    for index, color in enumerate(colors):
        c_id = str(color.get('id', ''))
        c_reference = color.get('reference', '')
        c_name = color.get('name', None).lower().strip()
        url = f'https://www.stradivarius.com/{c_code}/{json_data.get("productUrl", "")}?cS={color["id"]}&pelement={pid}'
        
        # Check if 'compositionDetail' exists before trying to access it
        upper, lining, sole, insole = extract_composition_details(color['compositionDetail']) if 'compositionDetail' in color else None
        origin = ','.join(color['traceability']['confection'].get('country', '')).lower()
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
            oldprice = float(size.get('oldPrice', 0) or 0) / 100
            if oldprice == 0 or oldprice == None:
                oldprice = price
            availability = available_remap(size.get('visibilityValue', None))
        
            entry = {
                "product_id": apid,
                "sub_brand": None,
                "gender": gender,
                "age_group": ['adult'],
                "age_range": ['18y'],
                "date_of_scraping": parse_launch_date(fetch_date),
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
                "sole_material": sole,
                "upper_material": upper,
                "closure_type": None,
                "toe_type": None,
                "heel_type": None,
                "weight": None,
                "heel_to_toe_drop": None,
                "occasion": None,
                "origin": origin,
                "images": images
            }
            all_products.append(entry)
    return all_products

# Function to log SKU details to CSV
def log_sku_details_to_csv(log_data, log_file):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    df = pd.DataFrame(log_data)
    df.to_csv(log_file, index=False)

def get_folders(sub_folders, exclude_folder = None):
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    # Filter out any folder that is in the exclude list
    return [folder for folder in folders if '.json' not in folder]

# Function to process a folder and log SKU details
def process_jsons(fetch_date, country, c_code):
    log_data = []
    gender_folder = os.path.join(country, 'Data', fetch_date, 'Json_data')
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
                    with open(file_path, 'r') as json_file:
                        data = json.load(json_file)
                    product_type = str(data.get('productType', '')).strip().lower()
                    if product_type != 'footwear':
                        continue
                    skus = create_individual_json(c_code, fetch_date, data)
                    if not skus:
                        continue
                    collection.insert_many(skus)
                    for sku in skus:
                        print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                        log_data.append({"file_path": file_path, "sku": sku["sku"], "status": 'new'})
                except Exception as e:
                    print(file_path)
                    print(e)
                    traceback.print_exc()
    
    # Log SKU details to Excel after processing the folder
    log_file = os.path.join(country, 'Data', fetch_date, 'Db_data', f'sku_log_{fetch_date}.csv')
    log_sku_details_to_csv(log_data, log_file)
    print(f'SKU log for {country} {fetch_date} is now saved')

if __name__ == "__main__":
    # Get today's date and format it
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Tuesday', 'Thursday', 'Saturday','Friday']:
        # Database details
        connection_string = "mongodb://localhost:27017"
        client = pymongo.MongoClient(connection_string)
        db = client['tg_analytics']
        collection = db['crawler_sink_stradivarius_saudi_footwear']
        
        # Define countries and their codes
        countries = {
            'Saudi' : 'sa/en'
        }

        # Process folder and log SKU details
        print(f"Processing data for {today_str} in saudi...")
        for country, c_code in countries.items():
            # Process folder and log SKU details
            process_jsons(today_str, country, c_code)

        client.close()
    else:
        print(f"Today is {day}. No data processing required for saudi {today_str}.")