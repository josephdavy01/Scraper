import logging
import os
import json
import re
from urllib.parse import urljoin
import pymongo
import traceback
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
    for fmt in (format_string_with_ms, format_string_without_ms, format_string_date_only):
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    logging.warning(f"Unknown date format: {date_string}")
    return datetime.utcnow()

def get_image_style(image_list):
    images = []
    for image in image_list:
        if "&wid=566&hei=708&size=566%2C708" in image:
            image = image.replace(
                "&wid=566&hei=708&size=566%2C708",
                "&wid=1080&hei=1080&size=1080%2C1080"
            )
            image_style = 'n_f_f_c' if '_HF' in image else 's0'
            images.append({
                "url": image,
                "image_style": image_style
            })
    return images

def get_gender(json_data):
    category = str(json_data.get("Gender", json_data.get("Gender", "")))
    if "Men" in category:
        return "male"
    elif "Women" in category:
        return "female"
    elif "Kids" in category:
        return "kids"
    else:
        return "unisex"

def get_age_group(gender: str):
    if gender in ["male", "female"]:
        return ["adult"]
    if gender == "kids":
        return ["kids"]
    return ["adult"]

def get_age_range(gender: str):
    if gender in ["male", "female"]:
        return ["18y"]
    if gender == "kids":
        return ["1y", "17y"]
    return ["18y"]

def create_individual_json(today_str, json_data, file_name):
    all_products = []
    color_name = json_data.get("Color").lower()
    sku_base = json_data["json_ld"].get("sku", "").replace("UA","").strip()
    cid = sku_base.split('-')[-1] if sku_base else None
    pid = f'uar{sku_base.split("-")[0]}'.replace("UA","").strip()
    url = json_data.get('url')
    name = str(json_data["json_ld"].get("name", "")).lower().strip()
    description = json_data["json_ld"].get('description', "")
    extra_description = json_data.get('extra description') or json_data.get('extra_description')
    if extra_description:
        full_description = description + "\n" + str(extra_description)
    else:
        full_description = description

    gender = get_gender(json_data)
    age_group = get_age_group(gender)
    age_range = get_age_range(gender)

    current_price = None
    current_price = json_data.get('SalePrice')
    if not current_price or current_price == 0:
        return
    if not current_price:
        current_price = json_data.get("OriginalPrice")
    launch_price = None  
    launch_price = json_data.get('OriginalPrice')
    if not launch_price:
        launch_price = json_data.get('SalePrice')

    weight = json_data.get("Weight")
    if not weight:
        weight = None
    images_list = json_data.get('Images')
    activity = str(json_data.get("occasion", "")).lower()
    if activity == "":
        activity = None
    elif activity == "football_soccer":
        activity = "football"
    

    for product in json_data.get("Sizes", []):
        size = product.get("size").replace(" ","")
        sku = f"{sku_base}-{size}" 
        availability = product.get("status", "")
        if "In Stock" in availability:
            stock = "in_stock"
        elif "Out of Stock" in availability:
            stock = "out_of_stock"

        entry = {
            "product_id": pid,
            "gender": gender,
            "age_group": age_group,
            "age_range": age_range,
            "date_of_scraping": datetime.strptime(today_str, "%Y-%m-%d"),
            "url": url,
            "title": name,
            "sub_brand": None,
            "description": full_description,
            "product_ref_code": None,
            "color_id": f'{pid}%{cid}',
            "color_name": color_name,
            "color_ref_code": None,
            "sku": f'{pid}%{sku}',
            "size_name": size,
            "size_ref_code": None,
            "price": float(current_price),
            "launch_price": float(launch_price),
            "availability": stock,
            "sole_material": None,
            "upper_material": None,
            "occasion": activity,
            "shoe_type": None,
            "closure_type": None,
            "toe_shape": None,
            "heel_type": None,
            "weight": weight,
            "heel_to_toe_drop": None,
            "origin": None,
            "images": get_image_style(images_list)
        }
        all_products.append(entry)

    return all_products

def process_jsons(today_str, country, collection):
    base_path = os.path.join(country, 'Data', today_str, 'Json_data')

    if not os.path.exists(base_path):
        logging.warning(f"Directory {base_path} does not exist.")
        return

    genders = [g for g in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, g))]
    for gender in genders:
        gender_folder = os.path.join(base_path, gender)
        categories = [c for c in os.listdir(gender_folder) if os.path.isdir(os.path.join(gender_folder, c))]
        for category in categories:
            category_folder = os.path.join(gender_folder, category)
            files = [f for f in os.listdir(category_folder) if f.endswith('.json')]
            for file in files:
                file_path = os.path.join(category_folder, file)
                logging.info(f"Processing file: {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        json_data = json.load(json_file)

                    shoe_list = create_individual_json(today_str, json_data, file)
                    if shoe_list:
                        category_value = json_data.get("Division")
                        for sku in shoe_list:
                            logging.info(f'Product_id: {sku["product_id"]}, SKU: {sku["sku"]}, Color: {sku["color_name"]}')
                        if category_value and "footwear" in category_value:
                            logging.info(f'Category: {category_value} (File: {file})')
                            collection.insert_many(shoe_list, ordered=False)
                            logging.info(f"Inserted {len(shoe_list)} documents from {file_path}")
                        else:
                            logging.info(f"{category_value} skipping {file_path} ")                            
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON in {file_path}: {e}")
                except Exception as e:
                    logging.error(f"Error processing {file_path}: {e}")
                    traceback.print_exc()

if __name__ == "__main__":
    today_str = date.today().strftime("%Y-%m-%d")
    # today_str = '2025-11-26'
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = ['UAE']

    for country in countries:
        collection = db[f'crawler_sink_underarmour_{country.lower()}_footwear']
        # for today_str in os.listdir(f"{country}/Data"):
            # process_jsons(today_str, country, collection)
        process_jsons(today_str, country, collection)
    client.close()
