#!/usr/bin/env python3
import os
import json
import pymongo
import traceback
import logging
import pandas as pd
from datetime import date, datetime

# ==================== LOGGING CONFIG ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("next_load_to_db.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ==================== HELPERS ====================

def parse_launch_date(date_string):
    """Parse ISO date formats safely."""
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    logging.warning(f"Unknown date format: {date_string}")
    return datetime.utcnow()

def remap_gender(gender):
    if gender == 'Men':
        return 'male'
    elif gender == 'Women':
        return 'female'
    return 'unisex'

def get_images(imagelist):
    images = []
    for image in imagelist:
        url = f"https://xcdn.next.co.uk{image['imageUrl']}"
        if image['shotType'] == 'SIP Still Life' and image['imageType'] == 'M':
            image_style = 'n_f_f_c'
        elif image['shotType'] == 'SIP Still Life' and image['imageType'] == 'B':
            image_style = 'n_b_f_c'
        else:
            image_style = 's0'
        images.append({"url": url, "image_style": image_style})
    return images

# ==================== CORE FUNCTION ====================

def create_individual_json(today_str, product, gender):
    """Build a list of product SKUs. Return [] if any size has None price."""
    all_products = []
    pid = product.get('styleNumber')
    cid = product.get('itemNumber')
    name = (product.get('title') or '').lower()
    cname = (product.get('colour') or '').lower().strip()
    gender = remap_gender(gender)
    url = f"https://www.nextdirect.com/in/en/style/{pid}/{cid}"
    reference = product.get('productCode')
    description = product.get('itemDescription', {}).get('toneOfVoiceSanitised')
    composition = product.get('itemDescription', {}).get('composition')
    origin = product.get('itemDescription', {}).get('countryOfOrigin')
    images = get_images(product.get('itemMedia', []))
    mpid = 'nxt' + pid

    # --- CHECK if any size has None price ---
    sizes = product.get('options', {}).get('options', [])
    if not sizes:
        logging.warning(f"No sizes found for product {pid}, skipping file.")
        return []

    for s in sizes:
        if s.get('priceUnformatted') is None:
            logging.warning(f"Null price found in {pid}, skipping this product file.")
            return []  # skip entire product file

    for size in sizes:
        sizeid = size.get('value')
        sizename = (size.get('name') or '').strip()
        sku = f"p{pid}c{cid}s{sizeid}"

        stock_status = size.get('stockStatus')
        if stock_status == 'InStock':
            availability = 'in_stock'
        elif stock_status == 'SoldOut':
            availability = 'out_of_stock'
        else:
            availability = 'out_of_stock'

        price = float(size['priceUnformatted'])

        if product.get('priceData', {}).get('wasPrice') is None:
            oldprice = price
        else:
            price_data = product['priceData']
            try:
                oldmin = price_data['price']['minPrice']
                oldmax = price_data['price']['maxPrice']
                newmin = price_data['salePrice']['minPrice']
                newmax = price_data['salePrice']['maxPrice']
                dis_percentage = int(((((oldmax - newmax) / oldmax) +
                                       ((oldmin - newmin) / oldmin)) / 2) * 100)
                oldprice = float(round(price / (100 - dis_percentage) * 100))
            except Exception:
                oldprice = price

        entry = {
            "product_id": mpid,
            "gender": gender,
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": name,
            "description": description,
            "product_ref_code": reference,
            "color_id": f"{mpid}%{cid}",
            "color_name": cname,
            "color_ref_code": None,
            "sku": f"{mpid}%{sku}",
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

# ==================== MAIN PROCESS ====================

keys = ["Boots", "Sandals", "Shoes", "Slippers", "Trainers", "Wellies", "Swim Shoes"]

def process_jsons(today_str, country):
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = ["Men","Women","Women Dresses","Women Lingerie","Men Suits","Men Nightwear","Men Underwear","Women Workwear","Women Swimwear"]
    for gender in genders:
        folder_path = os.path.join(gender_folder, gender)
        if not os.path.exists(folder_path):
            logging.warning(f"Missing folder: {folder_path}")
            continue

        files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
        for file in files:
            file_path = os.path.join(folder_path, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as jf:
                    data = json.load(jf)
                skus = create_individual_json(today_str, data, gender)

                if not skus:
                    logging.warning(f"Skipped file due to missing price: {file_path}")
                    continue

                category = data.get("category")
                if category in keys:
                    for sku in skus:
                        collection.insert_one(sku)
                    logging.info(f"Inserted {len(skus)} SKUs from {file}")
                else:
                    logging.info(f"Skipping file {file} (category not in keys).")

            except Exception:
                logging.exception(f"Error processing file: {file_path}")

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-06'
    countries = ['UAE']
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    for country in countries:
        global collection
        collection = db[f'crawler_sink_next_{country.lower()}_footwear']
        process_jsons(today_str, country)

    client.close()
