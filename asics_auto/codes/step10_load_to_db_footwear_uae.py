import os
import json
import pymongo
import traceback
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
    
def remap_gender(json_data):
    gender_val = str(json_data.get('gender', '')).strip()
    gender_val = gender_val.split("'")[0].lower().strip()
    if gender_val == "women":
        return 'female'
    elif gender_val == "men":
        return 'male'
    elif gender_val == "big kids":
        return 'kids'
    else:
        return 'unisex'
    
def get_colorid(sku: str) -> str:
    if not sku or not isinstance(sku, str):
        return ""
    parts = sku.split("-")
    return parts[-1].strip() if len(parts) > 1 else ""

    
def is_footwear(json_data):
    try:
        product = json_data.get("product", {})
        gender = product.get("gender", "").lower()
        footwear_keywords = ["shoe", "shoes", "sneaker", "trainer", "boot", "cleat", "sandal"]

        return any(keyword in gender for keyword in footwear_keywords)
    except Exception:
        return False

def get_age_group(gender):
    if gender in ['female', 'male']:
        return ['adult']
    if gender == 'kids':
        return ['kids']
    return ['adult']

def get_age_range(gender):
    if gender in ['female', 'male']:
        return ['18y']
    if gender == 'kids':
        return ['1y', '17y']
    return ['18y']

def full_descriptions(json_data):
    description = json_data.get("desc", "")

    tech_features = json_data.get('tech_features', [])
    if tech_features:
        features = []
        for line in tech_features:
            if line != '':
                features.append(line)
        description += '\n' + ' | '.join(features)
    return description

def extract_prices(json_data):
    offers = json_data.get("offers", {})

    def to_float(val):
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    price = to_float(offers.get("lowPrice"))
    launch_price = to_float(offers.get("highPrice"))

    return {
        "launch_price": launch_price,
        "price": price
    }

def get_image_style(image_list):
    images = []
    for image in image_list:
        image = image.replace('7363676a114b197e63403a5271223fdb', '7a53c16109c576b004801c61c9184a99')
        temp = {
            "url": image,
            "image_style": 's0'
        }
        images.append(temp)

    if images:
        images[2]['image_style'] = 'n_f_f_c'
    return images 

def create_individual_json(today_str, json_data, gender):
    all_products = []
    if not json_data or not isinstance(json_data, dict):
        return []

    if not is_footwear(json_data):
        return []

    product = json_data.get("product", {})
    inner_product = product.get("product", {})

    name = inner_product.get('name', '').lower()
    url = product.get('url', '')     
    gender = remap_gender(product)   
    product_id = 'asi' + inner_product.get('sku', '').split('-')[0]
    descriptions = full_descriptions(product)   
    cid = get_colorid(inner_product.get('sku', ''))
    raw_images = product.get('images', [])      
    images = get_image_style(raw_images)
    prices = extract_prices(inner_product)
    price = prices["price"]
    launch_price = prices["launch_price"]

    availibility = product.get("available_sizes", [])   
    if not availibility:
        return []

    color_name = product.get('cname', '').strip().lower()
    if not color_name:
        return []   # skip this product if color_name is missing
    
    for size in availibility:
        size_name = size.strip()
        if not size_name:
            continue

        size_specific_sku = f"{product_id}%{product_id.replace('asi', '')}.{cid}.{size_name}"
        availability = "in_stock"  

        entry = {
            "product_id": product_id,
            "sub_brand": None,
            "gender": gender,
            "age_group": get_age_group(gender),
            "age_range": get_age_range(gender),
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": name,
            "description": descriptions,
            "product_ref_code": None,
            "color_id": f'{product_id}%{cid}',
            "color_name": color_name,
            "color_ref_code": cid,
            "sku": size_specific_sku,
            "size_name": f'EU {size_name}',
            "size_ref_code": None,
            "price": price,
            "launch_price": launch_price,
            "availability": availability,
            "sole_material": None,
            "upper_material": None,
            "closure_type": None,
            "toe_shape": None,
            "heel_type": None,
            "weight": None,
            "heel_to_toe_drop": None,
            "occasion": None,
            "origin": None,
            "images": images
        }
        all_products.append(entry)
    return all_products

def get_folders(sub_folders, exclude_folder=None):
    if exclude_folder is None:
        exclude_folder = []
    if not os.path.exists(sub_folders):
        return []
        
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    return [folder for folder in folders if '.json' not in folder]


def process_jsons( today_str, country,collection):
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
                    if skus:
                        collection.insert_many(skus)
                        for sku in skus:
                            print(f'Product_id: {sku["product_id"]}, SKU: {sku["sku"]}')
                    else:
                        print(f"Skipping {file} - not footware or missing data")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-06'
    # today_str = '2025-11-29'
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    
    countries = ['UAE']
    
    for country in countries:
        collection = db[f'crawler_sink_asics_{country.lower()}_footwear']
        print(f"Processing {country} footwaear...")
        process_jsons( today_str, country, collection)
        print(f"Footware data loading for {country} completed!")
    
    client.close()