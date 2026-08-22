import os
import json
import re
import pymongo
import traceback
import pandas as pd
from bs4 import BeautifulSoup
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
        
def remap_gender(gender):
    gender_mapping = {
        'men': 'male',
        'women': 'female'
    }
    return gender_mapping.get(gender, 'unisex')

def get_images(media):
    images = []
    for item in media:
        if 'src' in item:
            url = item['src']
            style = 's0'
            images.append({
                "url": url,
                "image_style": style
            })
    return images

# Fixed version of create_individual_json
def create_individual_json(today_str, product_data, gender):
    all_products = []
    product = product_data['props']['pageProps']['productData']['product']
    name = product['title'].lower().strip()
    gender = remap_gender(gender)
    url = f"https://uk.gymshark.com/products/{product['handle']}"
    
    description_text = product['description']
    description_text = re.sub(r'<[^>]+>', '', description_text)
    start = description_text.find('•')
    end = description_text.find('SIZE')

    if start != -1 and end != -1:
        description = description_text[start:end]
        description = description.replace('•', '.').strip().strip('.') + '.'
    else:
        soup = BeautifulSoup(product['description'], "html.parser")
        p_tags = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]

        description = ""
        if p_tags:
            for txt in p_tags:
                if not txt.isupper() and len(txt.split()) > 3:  
                    description = txt
                    break

    composition = re.sub(r'<[^>]+>', '', description_text)
    match = re.search(r'\d+%[^.\n]+(?:, *\d+%[^.\n]+)*', description_text)
    if match:
        composition = match.group(0).strip()

    old_price = product['compareAtPrice']
    cname = product['colour'].lower().strip()
    images = get_images(product['media'])

    for size in product['availableSizes']:
        sku = size['sku']
        sku_split = sku.split('-')
        pid = 'gym' + sku_split[0]
        cid = sku_split[1]
        sname = sku_split[2]
        price = size['price']
        if not price or price == 0:
            continue
        if old_price is None:
            old_price = price
        if size['inStock'] == True:
            availability = 'in_stock'
        else:
            availability = 'out_of_stock'

        entry = {
            "product_id": pid,
            "gender": gender,
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
            "size-_name": sname,
            "size_ref_code": None,
            "price": price,
            "launch_price": old_price,
            "availability": availability,
            "demand": None,
            "composition": composition,
            "origin": None,
            "images": images
        }
        all_products.append(entry)
    return all_products

def get_folders(sub_folders, exclude_folder=None):
    folders = os.listdir(sub_folders)
    if exclude_folder:
        folders = [folder for folder in folders if folder not in exclude_folder]
    return [folder for folder in folders if not folder.endswith('.json')]

def process_jsons(today_str, country, collection):
    log_data = []
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = get_folders(gender_folder, [])
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, [])
        for category in categories:
            file_folder = os.path.join(category_folder, category)
            files = os.listdir(file_folder)
            for file in files:
                file_path = os.path.join(file_folder, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    skus = create_individual_json(today_str, data, gender)
                    for sku in skus:
                        print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                        collection.insert_one(sku)
                        log_data.append({"file_path": file_path, "sku": sku["sku"], "status": 'new'})
                except Exception as e:
                    print(file_path)
                    print(e)
                    traceback.print_exc()

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-10-17'

    countries = ['UK']

    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    for country in countries:
        collection = db[f'crawler_sink_gymshark_{country.lower()}']
        process_jsons(today_str, country)

    client.close()
