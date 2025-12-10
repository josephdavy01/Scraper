import logging
import os
import json
import traceback
from datetime import date, datetime
from validations import save_json

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constants ---
base_url = "https://static.bershka.net/4/photos2/"
video_url = "https://static.bershka.net/"

# --- HELPER: Serializer for Date Objects (Required for JSON file saving) ---
def datetime_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# Function to get the style of an image based on its filename
def get_image_style(image_urls):
    images = []
    for name, url in image_urls.items():
        filename = url.split('/')[-1].split('.')[0]
        image_style = 's0'

        if '3_1_0' not in filename:
            if name == 'a1t':
                image_style = 'm_b_f_c'
            elif name == 'a3o':
                image_style = 'm_f_f_c'
            elif name == 'a4o':
                image_style = 'n_f_f_c'
            elif name in ['b', 'b1']:
                image_style = 'n_b_f_c'
            elif name in ['p', 'p1']:
                image_style = 'm_f_n_c'
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
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            return datetime.strptime(date_string, format_string_date_only)

def get_image_urls(colorcode, xmedia):
    temp = {}
    for tempmedia in xmedia:
        if tempmedia['colorCode'] == colorcode:
            for j in tempmedia['xmediaItems']:
                for k in j['medias']:
                    extrainfo = k.get('extraInfo', '')
                    if extrainfo:
                        name = extrainfo.get('originalName', '')
                        url = extrainfo.get('url', '')
                        if name and url:
                            if '.mp4' in url or 'assets/public' in url:
                                temp[name] = video_url + url
                            else:
                                temp[name] = base_url + url
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
        "HIDDEN" : "out_of_stock",
        "RUNNING_OUT" : "low_on_stock"
    }
    return availability_map[avail]

# Function to create individual JSON objects for each SKU
def create_individual_json(c_code, today_str, file_path, json_data):
    all_products = []

    product = json_data['products'][0]
    if not product:
        logging.info(f"Error: No product found in {file_path}")
        return []

    productType = product.get('productType', '').lower().strip()
    
    if productType== "clothing":

        name = product.get('nameEn', '').lower()
        pid = str(product.get('id', ''))
        cat = file_path.split(os.sep)[-2]
        gender = file_path.split(os.sep)[-3]
        gender = product.get('sectionNameEN', '')
        if gender == 'MEN':
            gender = 'male'
        if gender == 'WOMEN':
            gender = 'female'
        if cat == 'unisex':
            gender = 'unisex'

        description = product['bundleProductSummaries'][0]['detail'].get('description', '')
        if description == '':
            description = None
        reference = product['bundleProductSummaries'][0]['detail'].get('reference', '')
        apid = 'bka' + reference.split('-')[0]
        
        colors = product['bundleProductSummaries'][0]['detail'].get('colors', [])
        xmedia = product['bundleProductSummaries'][0]['detail'].get('xmedia', [])
        for index, color in enumerate(colors):
            c_id = str(color.get('id', ''))
            c_reference = color.get('reference', '')
            c_name = color.get('name', '').lower().strip()
            if c_name == '':
                c_name = None
            url = f'https://www.bershka.com/{c_code}/{name}-c0p{pid}.html?colorId={c_id}'
            
            # Check if 'compositionDetail' exists before trying to access it
            composition = extract_composition_details(color['compositionDetail']) if 'compositionDetail' in color else ''
            
            image_urls = get_image_urls(c_id, xmedia)
            if image_urls:
                images = get_image_style(image_urls)
            else:
                images = []
            
            for size in color.get('sizes', []):
                sku = str(size.get('sku', ''))
                sizename = size.get('name', '')
                sizereference = size.get('partnumber', '')
                
                raw_price = size.get("price")
                price = float(raw_price) / 100 if raw_price else 0
                if price == 0:
                    continue

                # oldprice
                raw_old = size.get("oldPrice")
                oldprice = float(raw_old) / 100 if raw_old else price

                origin = size.get('country', '').lower()
                if origin == '':
                    origin = None
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
    all_country_data = [] # List to collect all products for this country
    
    gender_folder = os.path.join(country, today_str, 'Json_data')
    
    # Add check to avoid crashing if folder doesn't exist
    if not os.path.exists(gender_folder):
        logging.warning(f"Data folder not found for {country}: {gender_folder}")
        return []

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
                        raw = json_file.read().strip()
                        if not raw:
                            logging.info(f"Data is empty, skipping JSON file: {file_path}")
                            continue
                        data = json.loads(raw)
                    
                    skus = create_individual_json(c_code, today_str, file_path, data)
                    
                    if skus:
                        # CHANGED: Append to list instead of inserting to DB
                        all_country_data.extend(skus)
                        
                        # Optional: Keep logging if you want to see progress
                        # for sku in skus:
                        #     logging.info(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                    else:
                        logging.info(f"No clothing SKUs found in {file_path}")
                                              
                except Exception as e:
                    logging.info(file_path)
                    logging.info(e)
                    traceback.print_exc()
    
    return all_country_data

if __name__ == "__main__":
    # Removed Database details
    # connection_string = "mongodb://localhost:27017"
    # client = pymongo.MongoClient(connection_string)
    # db = client['tg_analytics']

    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-11-13'

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = {
            'Canada' : 'ca',
            'India' : 'in',
            'Saudi' : 'sa/en',
            'Spain' : 'es/en'
            }
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = {
            'Turkey' : 'tr/en',
            'UAE' : 'ae',
            'UK' : 'gb',
            'USA' : 'us'
            }
    else:
        countries = {}
        
    for country, c_code in countries.items():
        logging.info(f"Processing {country}...")
        
        # 1. Collect data (Removed DB collection assignment)
        country_data = process_jsons(today_str, country, c_code)

        # 2. Save to Local File
        if country_data:
            # Define output path (e.g., Country/Date/country_data_clothing.json)
            output_dir = os.path.join(country, today_str)
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f'{country}_data_clothing.json')

            try:
                save_json(output_file, country_data, default=datetime_serializer)
                logging.info(f"SUCCESS: Saved {len(country_data)} items to {output_file}")
            except Exception as e:
                logging.error(f"Failed to save JSON file for {country}: {e}")
        else:
            logging.info(f"No data collected for {country}.")

    # client.close()