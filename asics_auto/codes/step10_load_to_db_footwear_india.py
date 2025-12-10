import os
import json
import pymongo
import traceback
import html as html_module
from datetime import datetime
from bs4 import BeautifulSoup

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
    if gender in ['women', 'girls', 'girl', 'woman']:
        return 'female'
    elif gender in ['men', 'boys', 'boy', 'man']:
        return 'male'
    elif gender in ['kids', 'kid']:
        return 'kids'
    else:
        return 'unisex'
    
def remap_occasion(occasion):
    mapping = {
        "track & field" : "track & field",
        "cricket" : "cricket",
        "walking" : "walking",
        "running" : "running",
        "indoor court" : "indoor court",
        "training" : "training",
        "tennis" : "tennis",
        "sportstyle" : "lifestyle"
    }
    return mapping.get(occasion, occasion)

def get_images(media_entries):
    images = []
    for entry in media_entries:
        url = 'https://www.asics.co.in/media/catalog/product' + entry['file']
        if '_fr_' in url:
            image_style = 'n_f_f_c'
        else:
            image_style = 's0'
        temp = {
            "url": url,
            "image_style": image_style
        }
        images.append(temp)
    return images

def get_age_group(gender):
    if gender in ['female', 'male', 'unisex']:
        return ['adult']
    elif gender == 'kids':
        return ['kids']
    else:
        return ['adult']

def get_age_range(gender):
    if gender in ['female', 'male', 'unisex']:
        return ['18y']
    elif gender == 'kids':
        return ['1y', '17y']
    else:
        return ['18y']

def extract_text_from_html(html_content):
    # First decode HTML entities (like &lt; and &gt;)
    decoded_html = html_module.unescape(html_content)
    
    # Parse the HTML content
    soup = BeautifulSoup(decoded_html, "html.parser")
    
    # Remove style and script tags
    for tag in soup(["style", "script"]):
        tag.decompose()
    
    # Get all text, strip leading/trailing whitespace
    text = soup.get_text(separator="\n", strip=True)

    return text

# Function to create individual JSON objects for each SKU
def create_individual_json(today_str, json_data):
    all_products = []
    try:
        product = json_data['data']['products']['items'][0]
        name = f'{product['name'].lower()} - {product['product_sub_title'].lower()}'
        url_key = product['url_key']
        url = f"https://www.asics.co.in/{url_key}.html"
        description = extract_text_from_html(product['description']['html'])
        reference = product['sku']
        pid = 'asi' + reference.split('.')[0]
        cid = reference.split('.')[-1]
        cname = product['colour'].lower()
        attributes = product['custom_attributes']
        origin = None
        occasion = None
        product_type = None
        sole_material = None
        upper_material = None

        for attribute in attributes:
            metadata = attribute['attribute_metadata']['label'].strip()
            if metadata == 'Country of Origin':
                origin = attribute['selected_attribute_options']['attribute_option'][0]['label'].strip().lower()
            if metadata == 'Sole Material':
                sole_material = attribute['entered_attribute_value']['value'].strip().lower()
            if metadata == 'Upper Material':
                upper_material = attribute['entered_attribute_value']['value'].strip().lower()
            if metadata == 'PRODUCT TYPE':
                product_type = attribute['selected_attribute_options']['attribute_option'][0]['label'].strip().lower()
            if metadata == 'ACTIVITY':
                occasion = remap_occasion(attribute['selected_attribute_options']['attribute_option'][0]['label'].strip().lower())
            if metadata == 'GENDER':
                gender = remap_gender(attribute['selected_attribute_options']['attribute_option'][0]['label'].strip().lower())
                age_group = get_age_group(gender)
                age_range = get_age_range(gender)
            
        if not occasion:
            splits = product['product_sub_title'].lower().split(' ')
            occasion = ' '.join(splits[1:-1])
            occasion = remap_occasion(occasion)

        if product_type in ['shoes', 'flip flop and slides']:
            images = get_images(product['media_gallery_entries'])
            variants = product['variants']
            for variant in variants:
                sku = variant['product']['sku']
                availability = variant['product']['stock_status'].lower()
                price_data = variant['product']['price_range']['minimum_price']
                price = float(price_data['final_price']['value'])
                oldprice = float(price_data['regular_price']['value'])
                size_attributes = variant['product']['custom_attributes']

                sizename = None
                for size in size_attributes:
                    if size['attribute_metadata']['label'] == 'SIZE':
                        sizename = size['selected_attribute_options']['attribute_option'][0]['label'].strip()

                    if sizename:
                        entry = {
                            "product_id": pid,
                            "gender": gender,
                            "age_group": age_group,
                            "age_range": age_range,
                            "date_of_scraping": parse_launch_date(today_str),
                            "url": url,
                            "title": name,
                            "sub_brand": None,
                            "description": description,
                            "product_ref_code" : reference,
                            "color_id": f'{pid}%{cid}',
                            "color_name": cname,
                            "color_ref_code" : reference,
                            "sku": f'{pid}%{sku}',
                            "size_name": sizename,
                            "size_ref_code" : sku,
                            "price": price,
                            "launch_price": oldprice,
                            "availability": availability,
                            "sole_material": sole_material,
                            "upper_material": upper_material,
                            "occasion": occasion,
                            "closure_type": None,
                            "toe_shape": None,
                            "heel_type": None,
                            "weight": None,
                            "heel_to_toe_drop": None,
                            "origin": origin,
                            "images": images
                        }
                        all_products.append(entry)
            return all_products
        else:
            print(f"Skipping product {url_key} as it is not a footwear.")
            return []
    except:
        return []

def get_folders(sub_folders, exclude_folder = None):
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    # Filter out any folder that is in the exclude list
    return [folder for folder in folders if '.json' not in folder]

# Function to process a folder and log SKU details
def process_jsons(today_str, country):
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
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
                        data = json.load(json_file)
                    skus = create_individual_json(today_str, data)
                    if skus:
                        collection.insert_many(skus)
                        for sku in skus:
                            print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                except Exception as e:
                    print(file_path)
                    print(e)
                    traceback.print_exc()

if __name__ == "__main__":
    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    
    # Get today's date and format it
    today_str = datetime.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-06'
    
    country = 'India'

    collection = db[f'crawler_sink_asics_{country.lower()}_footwear']
    # Process folder and log SKU details
    process_jsons(today_str, country)

    client.close()