import os
import json
import re
import pymongo
import logging
from datetime import date, datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

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
    for img in image:
        url = img.get("src")
        style = 's0'
        images.append({
            "url": url,
            "image_style": style
        })
    return images


def get_gender(json_data):
    product = json_data.get("product", {})
    handle = product.get("handle", "").lower().replace("bauer-oofos-", "").strip()
    if handle.startswith('mens'):
        return "male"
    elif handle.startswith('womens'):
        return "female"
    else:
        return "unisex"
    
def get_pid(product_data, pdict):
    product_info = product_data.get('product', {})
    title = product_info.get('title', '')
    product_title = title.split('-')[0].split('–')[0].strip()
    for title_key, pid in pdict.items():
        if title_key.lower() in product_title.lower():
            return pid
    return None

def create_individual_json(today_str, product_data, cdict, pdict):
    all_products = []
    product = product_data.get("product", {})
    name = product.get('title', '').split("–")[0].lower().strip()
    images = get_images(product.get('images', []))
    url_parts = product.get('handle', '')
    url = f'https://www.oofos.com/products/{url_parts}'
    pid = get_pid(product_data, pdict)
    body_html = product.get('body_html', '').strip()
    description = re.sub(r'<[^>]+>', '', body_html).strip()
    variants = product.get("options", [])
    for variant in variants:
        if variant.get("name") in ["Colour", "Color"]:
            values = variant.get("values")
            if isinstance(values, list) and values:
                cname = values[0]

    cid = cdict.get(cname)

    for variant in product.get("variants", []):
        sku = variant.get('sku', '').lower()
        weight = variant.get("grams")
        if weight == 0:
            weight = None
        sname = variant.get("option1")
        availability = variant.get('inventory_quantity')
        stock_status = 'in_stock' if availability > 0 else 'out_of_stock'
        try:
            current_price = variant.get('price')
            old_price = variant.get('compare_at_price')
            if old_price in ["0","0.00", "null", "", None]:
                old_price = current_price

            price_val = float(current_price)
            launch_val = float(old_price)

            if price_val > 1000:
                price = int(price_val / 100)
                launch_price = int(launch_val / 100)
            else:
                price = int(price_val)
                launch_price = int(launch_val)

        except (ValueError, TypeError) as e:
            logging.info(f"Price conversion error for SKU {sku}: {e}")
            
        entry = {
            "product_id": pid,
            "gender": get_gender(product_data),
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": name,
            "description": description,
            "product_ref_code": None,
            "color_id": f'{pid}%{cid}',
            "color_name": cname.lower(),
            "color_ref_code": None,
            "sku": f'{pid}%{sku}',
            "size_name": sname,
            "size_ref_code": None,
            "price": price,
            "launch_price": launch_price,
            "availability": stock_status,
            "sole_material": None,
            "upper_material": None,
            "occasion": None,
            "closure_type": None,
            "toe_type": None,
            "heel_type": None,
            "weight": weight,
            "heel_to_toe_drop": None,
            "origin": None,
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
    keys = ["clog","shoe","slide","thong","slipper",'boot']
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

                    if isinstance(data, str):
                        data = json.loads(data)
                    
                    category_filter = data.get("product", {}).get('product_type', '').lower().strip()
                    if category_filter in keys:
                        skus = create_individual_json(today_str, data, cdict, pdict)
                    if skus:
                        collection.insert_many(skus)
                        for sku in skus:
                            logging.info(f'Category_filter: {category_filter}, Product_id: {sku["product_id"]}, sku: {sku["sku"]}')
                    else:
                        logging.info(f"not a footwear {category_filter}")
                except json.JSONDecodeError as e:
                    logging.info(f"JSON decode error for {file_path}: {e}")
                except Exception as e:
                    logging.info(f"Error processing {file_path}: {e}")


if __name__ == "__main__":
    country = 'USA'
    today_str = date.today().strftime('%Y-%m-%d')
    connection_string = "mongodb://localhost:27017/"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    collection = db[f'crawler_sink_oofos_{country.lower()}_footwear']

    cid_path = 'oofos_cid_remapping.json'
    pid_path = 'oofos_pid_remapping.json'

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

    # data_path = os.path.join(country, 'Data')
    # for date_folder in os.listdir(data_path):
    process_jsons(today_str, country, collection, cdict, pdict)
    
    client.close()
