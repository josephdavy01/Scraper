import logging
import os
import json
import pymongo
import traceback
import pandas as pd
from datetime import date, datetime

# ---------- Helper Functions ---------- #

def parse_launch_date(date_string):
    """Parse multiple datetime formats safely."""
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

def remap_gender(gender):
    """Normalize gender labels."""
    gender = gender.lower().strip()
    if 'unisex' in gender:
        return 'unisex'
    if gender in ['men', 'boys', 'mens', 'mens;']:
        return 'male'
    elif gender in ['women', 'girls', 'womens', 'womens;']:
        return 'female'
    else:
        return 'unisex'

def get_pid(pid):
    """Map product handle to ID using pid remapping."""
    for i, j in pdict.items():
        if pid in j:
            return i
    return '0000000'

def get_images(imagelist):
    """Extract formatted image URLs."""
    images = []
    if not imagelist:
        return images

    for image in imagelist:
        src = image.get('src') or image.get('preview_image', {}).get('src')
        if not src:
            continue
        src = src.strip()
        temp = {
            "url": 'https:' + src,
            "image_style": 'm_f_f_c' if image.get('position') == 1 else 's0'
        }
        images.append(temp)
    return images

# ---------- Core Processing ---------- #

def create_individual_json(base_url, fetch_date, json_data, gender):
    """Create individual JSON entries for each SKU."""
    all_products = []
    product = json_data.get('product', {})
    descriptions = json_data.get('descriptions', {})

    # --- Extract safely ---
    description = descriptions.get('description', '').strip() or None
    composition = descriptions.get('composition', '').split("|")[0].strip() or None
    origin = descriptions.get('origin', None)

    name = product.get('title', '').lower()
    handle = product.get('handle', '')
    pid = 'usp' + get_pid(handle)
    cid = handle.split('-')[-1] if '-' in handle else '000'
    gender = remap_gender(gender)
    url = base_url + handle

    # Use 'media' if available, otherwise fallback to 'images'
    media_list = product.get('media') or []
    if not media_list and 'images' in product:
        # Create media-like structure if only 'images' exist
        media_list = [{"src": img, "position": i+1} for i, img in enumerate(product.get('images', []))]
    images = get_images(media_list)

    variants = product.get('variants', [])
    for size in variants:
        cname = size.get('option3', '').strip().lower()
        sku = size.get('sku')
        sizename = size.get('option1')
        price = float(size.get('price', 0)) / 100
        if not price or price == 0:
            continue

        oldprice = float(size.get('compare_at_price', 0)) / 100
        stock = size.get('available', False)
        availability = 'in_stock' if stock else 'out_of_stock'

        entry = {
            "product_id": pid,
            "gender": gender,
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(fetch_date),
            "url": url,
            "title": name,
            "description": description,
            "product_ref_code": None,
            "color_id": f'{pid}%{cid}',
            "color_name": cname,
            "color_ref_code": None,
            "sku": f'{pid}%{sku}',
            "size_name": sizename,
            "size_ref_code": None,
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

def log_sku_details_to_csv(log_data, log_file):
    """Write SKU log data to CSV."""
    df = pd.DataFrame(log_data)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    df.to_csv(log_file, index=False)

def get_folders(sub_folders, exclude_folder=None):
    """Return subfolder list excluding certain names."""
    folders = os.listdir(sub_folders)
    if exclude_folder:
        folders = [folder for folder in folders if folder not in exclude_folder]
    return [folder for folder in folders if '.json' not in folder]

def process_jsons(base_url, fetch_date, country):
    """Main pipeline to process JSON and insert into MongoDB."""
    log_data = []
    gender_folder = os.path.join(country, 'Data', fetch_date, 'Json_data')
    genders = get_folders(gender_folder, ['KIDS'])

    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, [])
        print(f"Processing gender: {gender}, categories: {categories}")

        for category in categories:
            file_folder = os.path.join(category_folder, category)
            files = os.listdir(file_folder)

            for file in files:
                file_path = os.path.join(file_folder, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)

                    skus = create_individual_json(base_url, fetch_date, data, gender)

                    if category.lower() in [k.lower() for k in keys]:
                        for sku in skus:
                            print(f'Category:{category}, Product_id:{sku["product_id"]}, SKU:{sku["sku"]}')
                            collection.insert_one(sku)
                            log_data.append({
                                "file_path": file_path,
                                "sku": sku["sku"],
                                "status": 'new'
                            })
                    else:
                        logging.info(f"Not an apparel category: {category}")

                except Exception as e:
                    print(f"Error in file: {file_path}")
                    print(e)
                    traceback.print_exc()

    # Save SKU log
    log_file = os.path.join(country, 'Data', fetch_date, 'Validation', f'sku_log_{fetch_date}.csv')
    log_sku_details_to_csv(log_data, log_file)
    print(f'SKU log for {country} ({fetch_date}) is now saved at: {log_file}')

# ---------- Main Execution ---------- #

if __name__ == "__main__":
    today = date.today()
    fetch_date = today.strftime('%Y-%m-%d')
    # fetch_date = '2025-12-06'

    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = {
        'India': 'https://uspoloassn.in/products/'
    }

    pid_path = 'us_polo_pid_remapping.json'
    if os.path.exists(pid_path):
        with open(pid_path, 'r') as json_file:
            pdict = json.load(json_file)
    else:
        pdict = {}

    # Categories reference list
    keys = [
        "2 piece", "Basic", "Blazers", "Boxers", "Briefs", "Cargos",
        "Casual jacket", "Chinos", "Cord set", "Dresses", "Gym vest", "Jackets",
        "Jeans", "Joggers", "Lounge pants", "Lounge t-shirts", "Padded jacket",
        "Polo shirt", "Polo shirts", "Sets", "Shirt", "Shirts", "Shorts", "Skirts",
        "Sweaters", "Sweatshirts", "T-shirt", "T-shirts", "Thermals", "Tops",
        "Track pants", "Trousers", "Trunks", "Vests", "Waistcoats"
    ]

    for country, base_url in countries.items():
        collection = db[f'crawler_sink_uspolo_{country.lower()}']
        process_jsons(base_url, fetch_date, country)

    client.close()
