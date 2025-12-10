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

def extract_compoition(json_data):
    key_features = json_data.get('key_features', [])
    for feature in key_features:
        if '%' in feature:
            return feature.strip()
    
    # If not found, check design_details
    design_details = json_data.get('design_details', [])
    for detail in design_details:
        if '%' in detail:
            return detail.strip()
    
    return None
    

def get_image_style(image_list):
    images = []
    for image in image_list:
        if '-5' in image:
            style = 'n_f_f_c'
        else:
            style = 's0'
        temp = {
            "url": image,
            "image_style": style
        }
        images.append(temp)
    return images

def get_age_group(gender):
    if gender in ['/womens', '/women', '/men', '/mens', '/unisex']:
        return ['adult']
    if gender in ['/boys', '/girls', '/toddlers']:
        return ['kids']
    return ['adult']

def get_age_range(gender):
    if gender in ['/womens', '/women', '/men', '/mens', '/unisex']:
        return ['18y']
    if gender in ['/boys', '/girls', '/toddlers']:
        return ['1y', '17y']
    return ['18y']

# Remapping genders
def remap_gender(gender):
    if gender in ['/womens', '/women', '/girls']:
        return 'female'
    if gender in ['/boys', '/men', '/mens']:
        return 'male'
    if gender in ['/unisex', '/toddlers']:
        return 'unisex'
    return 'unisex'

# Function to create individual JSON objects for each SKU
def create_individual_json(today_str, json_data, file_name):
    all_products = []
    try:
        generic = json_data['legal_metrology']['Generic Name'].lower()
        if generic in ['t-shirts', 't-shirt', 'tshirt', 'polo', 'tank tops', 'tank', 'tops', 'top', 'shirt', 'long sleeve tops', 'hoodie', 'hoodies', 'pants', 'pant', 'shorts', 'leggings', 'capris', 'jogger', 'cargo', 'jackets', 'jacket', 'dress', 'skirts and skorts', 'sports bra']:

            script_data = json_data['script_data']
            productreference = script_data['sku']
            pid = 'skr' + productreference.split('-')[0]
            cid = productreference.split('-')[1]
            url = json_data['url']

            name = script_data['name'].lower().strip()
            images = get_image_style(script_data['image'])
            description = json_data['full_description_text']

            analytics_data = json_data['analytics_data']
            raw_gender = analytics_data['ecommerce']['detail']['actionField']['list'].lower()
            gender = remap_gender(raw_gender)
            age_group = get_age_group(raw_gender)
            age_range = get_age_range(raw_gender)
            color = analytics_data['view_item']['color'].lower().strip()

            price = float(json_data['price']['new_price'].split('₹')[1].strip().replace(',', ''))
            if not price or price == 0:
                return
            oldprice = float(json_data['price']['old_price'].split('₹')[1].strip().replace(',', ''))
            composition=extract_compoition(json_data)
            origin = json_data['legal_metrology']['Country of Origin'].split(',')[0].lower().strip()

            for size in json_data['available_sizes']:
                size = size.strip()
                availability = 'in_stock'
                sku = f'{productreference}-{size}'
                entry = {
                    "product_id": pid,
                    "gender": gender,
                    "age_group": age_group,
                    "age_range": age_range,
                    "date_of_scraping": parse_launch_date(today_str),
                    "url": url,
                    "title": name,
                    "description": description,
                    "product_ref_code" : productreference,
                    "color_id": f'{pid}%{cid}',
                    "color_name": color,
                    "color_ref_code" : productreference,
                    "sku": f'{pid}%{sku}',
                    "size_name": size,
                    "size_ref_code" : sku,
                    "price": price,
                    "launch_price": oldprice,
                    "availability": availability,
                    "demand": None,
                    "composition":composition,
                    "origin": origin,
                    "images": images
                }
                all_products.append(entry)
        else:
            print(f"Skipping file {file_name} as it is not apparel.")
    except KeyError as e:
        print(f"KeyError: {e} in product {file_name}")
    return all_products

# In your process_jsons function
def process_jsons(today_str, country):
    base_path = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = os.listdir(base_path)
    for gender in genders:
        gender_folder = os.path.join(base_path, gender)
        categories = os.listdir(gender_folder)
        for category in categories:
            category_folder = os.path.join(gender_folder, category)
            files = os.listdir(category_folder)
            for file in files:
                file_path = os.path.join(category_folder, file)
                print(file_path)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    skus = create_individual_json(today_str, data, file)
                    if skus:
                        collection.insert_many(skus)
                        for sku in skus:
                            print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                except Exception as e:
                    print(e)
                    traceback.print_exc()

if __name__ == "__main__":
    # Get today's date
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-10-31'

    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = ['India']

    for country in countries:
        collection = db[f'crawler_sink_skechers_{country.lower()}']
        # Process folder and log SKU details
        process_jsons(today_str, country)
    client.close()