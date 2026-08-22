import os
import json
import pymongo
import logging
from datetime import date, datetime

logging.basicConfig(level=logging.INFO)

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
            try:
                return datetime.strptime(date_string, format_string_date_only)
            except ValueError:
                logging.info(f"Invalid date format: {date_string}")
                return None

def get_images(image):
    images = []
    for img in image or []:
        url = img
        style = 's0'
        images.append({
            "url": url,
            "image_style": style
        })
    return images

def get_pid(url, pdict):
    handle = url.split("/products/")[-1]
    for pid, plist in pdict.items():
        if handle in plist:
            return pid
    return None

def create_individual_json(today_str, product_data, cdict, pdict):
    all_products = []
    name = product_data.get('name', '').lower().strip()
    url = product_data.get('url', '')
    pid = get_pid(url, pdict)
    if pid:
        pid = 'ena' + pid
        description = product_data.get('description', '').strip()
        composition_lines = product_data.get('composition', '').split('\n')
        composition = composition_lines[0] if composition_lines and composition_lines[0] else None
        if 'color_name' in product_data:
            cname = product_data.get('color_name', '').replace('variant sold out or unavailable', '').strip().lower()
        else:
            cname = product_data.get('color', '').replace('variant sold out or unavailable', '').strip().lower()
        if cname != '':
            cid = cdict.get(cname, None)
            if cid:
                images = get_images(product_data.get('images', []))
                offers = product_data.get('offers', [])
                sizes = product_data.get('sizes', {})
                origin = product_data.get('origin')
                if isinstance(origin, str):
                    origin = origin.lower().strip()
                elif origin == '':
                    origin = None
                else:
                    origin = None

                for offer in offers:
                    sku = offer.get('sku', '').lower()
                    availability = offer.get('availability', '')
                    size_info = sizes.get(sku, {})
                    size_name = size_info.get('size', '')
                    stock_status = 'in_stock' if availability == 'http://schema.org/InStock' else 'out_of_stock'
                    try:
                        current_price = size_info.get('price')
                        price = round(float(current_price) / 100) 
                        old_price = size_info.get('old_price', price)
                        old_price = round(float(old_price) / 100) 
                        if old_price:
                            launch_price = old_price
                        else:
                            launch_price= price
                    except (ValueError, TypeError) as e:
                        logging.info(f"Price conversion error for SKU {sku}: {e}")
                    entry = {
                        "product_id": pid,
                        "gender": 'female',
                        "age_group": ['adult'],
                        "age_range": ['18y'],
                        "date_of_scraping": parse_launch_date(today_str),
                        "url": url,
                        "title": name,
                        "description": description,
                        "product_ref_code": None,
                        "color_id": f'{pid}%{cid}', 
                        "color_name": cname,
                        "color_ref_code": None,
                        "sku": f'{pid}%{sku}',
                        "size_name": size_name,
                        "size_ref_code": None,
                        "price": price,
                        "launch_price": launch_price,
                        "availability": stock_status,
                        "demand": None,
                        "composition": composition,
                        "origin": origin,
                        "images": images
                    }
                    all_products.append(entry)
    return all_products

def get_folders(sub_folders):
    try:
        folders = [folder for folder in os.listdir(sub_folders) if not folder.endswith('.json')]
        return folders
    except FileNotFoundError:
        logging.info(f"Directory not found: {sub_folders}")
        return []

def process_jsons(today_str, country, collection, cdict, pdict):
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = get_folders(gender_folder)
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder)
        for category in categories:
            file_folder = os.path.join(category_folder, category)
            try:
                files = os.listdir(file_folder)
            except FileNotFoundError:
                logging.info(f"Directory not found: {file_folder}")
                continue
            for file in files:
                file_path = os.path.join(file_folder, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)

                    skus = create_individual_json(today_str, data, cdict, pdict)
                    if skus:
                        collection.insert_many(skus)
                        for sku in skus:
                            logging.info(f'Product_id: {sku["product_id"]}, sku: {sku["sku"]}')

                except json.JSONDecodeError as e:
                    logging.info(f"JSON decode error for {file_path}: {e}")
                except Exception as e:
                    logging.info(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-10-22'

    country = 'India'

    # Database details
    connection_string = "mongodb://localhost:27017/"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    collection = db[f'crawler_sink_enamor_{country.lower()}']

    cid_path = 'enamor_cid_remapping.json'
    pid_path = 'enamor_pid_remapping.json'

    if os.path.exists(cid_path):
        with open(cid_path, 'r') as json_file:
            cdict = json.load(json_file)
    else:
        cdict = {}

    if os.path.exists(pid_path):
        with open(pid_path, 'r') as json_file:
            pdict = json.load(json_file)
    else:
        pdict = {}

    dates = os.listdir(f'{country}/Data')
    for today_str in dates:
        print(f'Processing date: {today_str}')
        process_jsons(today_str, country, collection, cdict, pdict)

    client.close()