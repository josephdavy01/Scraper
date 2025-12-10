import os
import json
import re
from urllib.parse import urljoin
import pymongo
import traceback
from datetime import date, datetime

base_url = 'https://www.underarmour.in'

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

def get_image_style(image_data):
    images = []
    for image in image_data:
        temp = {
            "url": image['large']['url'],
            "image_style": 's0'
        }
        images.append(temp)

    if images:
        images[len(images) - 1]['image_style'] = 'n_f_f_c'
    return images 

def remap_gender(gender):
    if str(gender).lower() == 'women':
        return 'female'
    elif str(gender).lower() == 'men':
        return 'male'
    else:
        return 'unisex'

def full_descriptions(data):
    short_desc_data = data.get("short_description", {}) or {}
    descriptions = short_desc_data.get("html", "")
    dna_html = data.get('dna')
    fit_care = data.get('fit_care', '')
    fit_care_cleaned = re.findall(r'<li>(.*?)</li>', fit_care, flags=re.DOTALL)
    list_items = re.findall(r'<li>(.*?)</li>', dna_html, flags=re.DOTALL)
    dna_separated = ' | '.join(list_items)
    combined_output = f"{descriptions}\n{dna_separated}\n{' | '.join(fit_care_cleaned)}"
    return combined_output

def get_price(price_dict):
    cprice = price_dict['final_price']['value']
    oprice = price_dict['regular_price']['value']

    # if price is 0 or missing, return None to signal skip
    if not cprice or cprice == 0:
        return None, None

    return cprice, oprice


def get_size_code(vattributes):
    for vattribute in vattributes:
        if vattribute['attribute_code'] == 'size':
            return vattribute['attribute_value']

def get_label_value(attribute_options):
    temp = []
    for option in attribute_options:
        temp.append({"label": option.get('label', '').lower().strip(), "value": option.get('value', '').lower().strip()})
    return temp

def get_label(value, id_list):
    for id in id_list:
        if id['value'] == value:
            return id['label']

def create_individual_json(today_str, json_data):
    all_products = []
    data = json_data['data']['products']['items'][0]
    gender = None
    activity = None
    shoe_type = None
    color_attribute_options = None
    size_attribute_options = None

    for attribute in data.get('attributes', []):
        if attribute.get('attribute_code') == 'gender':
            gender = attribute.get('attribute_options', [{}])[0].get('label').lower().strip()
        elif attribute.get('attribute_code') == 'sport':
            activity = attribute.get('attribute_options', [{}])[0].get('label').lower().strip()
        elif attribute.get('attribute_code') == 'shoe_type':
            shoe_type = attribute.get('attribute_options', [{}])[0].get('label').lower().strip()
        elif attribute.get('attribute_code') == 'color':
            color_attribute_options = attribute.get('attribute_options', [])
        elif attribute.get('attribute_code') == 'size':
            size_attribute_options = attribute.get('attribute_options', [])
        
    if shoe_type:
        color_id_list = get_label_value(color_attribute_options)
        size_id_list = get_label_value(size_attribute_options)

        product_id = 'uar' + data['sku']
        name = data['name'].lower().strip()
        gender = remap_gender(gender)
        main_url = base_url + data['url']
        descriptions = full_descriptions(data)
        specs = data.get("specs")
        match = re.search(r"(\d+)\s*grams", specs)
        if match:
            weight = str(match.group(1)) + 'g'
        else:
            weight = None

        match = re.search(r"(\d+)\s*mm", specs)
        if match:
            heel_to_toe_drop = str(match.group(1)) + 'mm'
        else:
            heel_to_toe_drop = None

        if weight and heel_to_toe_drop:
            descriptions += '\n' + f'Weight: {weight}, Heel to toe drop: {heel_to_toe_drop}'
        elif weight:
            descriptions += '\n' + f'Weight: {weight}'
        elif heel_to_toe_drop:
            descriptions += '\n' + f'Heel to toe drop: {heel_to_toe_drop}'

        origins = data.get('specs', '').split(':')[-1].strip()
        origin = re.sub(r'<.*?>', '', origins).lower().strip()

        variants = data['variants']
        for variant in variants:
            vdata = variant['product']
            vattributes = vdata['attributes']
            price_dict = vdata['price_range']['minimum_price']
            image_data = vdata['media_gallery_entries']

            cid = str(vdata['color'])
            cname = get_label(cid, color_id_list)
            url = f'{main_url}?color={cid}'
            sku = vdata['sku']
            size_ref_code = get_size_code(vattributes)
            sizename = get_label(size_ref_code, size_id_list)
            availiablity = vdata['stock_status'].lower().strip()
            price, old_price = get_price(price_dict)
            images = get_image_style(image_data)
            if cname:
                entry = {
                    "product_id": product_id,
                    "gender": gender,
                    "age_group": ['adult'],
                    "age_range": ['18y'],
                    "date_of_scraping": parse_launch_date(today_str),
                    "url": url,
                    "title": name,
                    "sub_brand": None,
                    "description": descriptions,
                    "product_ref_code": None,
                    "color_id": f'{product_id}%{cid}' ,
                    "color_name": cname,  
                    "color_ref_code": None,
                    "sku": f'{product_id}%{sku}',
                    "size_name": sizename,
                    "size_ref_code": None,
                    "price": price,
                    "launch_price": old_price,
                    "availability": availiablity,
                    "sole_material": None,
                    "upper_material": None,
                    "occasion": activity,
                    "shoe_type": shoe_type, 
                    "closure_type": None,
                    "toe_shape": None,
                    "heel_type": None,
                    "weight": weight,
                    "heel_to_toe_drop": heel_to_toe_drop,
                    "origin": origin,
                    "images": images
                }
                all_products.append(entry)
    return all_products

def process_jsons(today_str, country):
    base_path = os.path.join(country, 'Data', today_str, 'Json_data')
    
    if not os.path.exists(base_path):
        print(f"Directory {base_path} does not exist.")
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
                print(f"Processing file: {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:  
                        data = json.load(json_file)

                    skus = create_individual_json(today_str, data)
                    if skus:
                        collection.insert_many(skus)
                        for sku in skus:
                            print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                    else:
                        print(f"No SKUs generated for file: {file_path}")
                except:
                    try:
                        with open(file_path, 'r', encoding='utf-16') as json_file:  
                            data = json.load(json_file)

                        skus = create_individual_json(today_str, data)
                        if skus:
                            collection.insert_many(skus)
                            for sku in skus:
                                print(f'Product_id : {sku["product_id"]}, SKU : {sku["sku"]}')
                        else:
                            print(f"No SKUs generated for file: {file_path}")
                    except Exception as e:
                        print(f"Error processing file {file_path}: {e}")
                        traceback.print_exc()

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-05'
    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = ['India']

    for country in countries:
        collection = db[f'crawler_sink_underarmour_{country.lower()}_footwear']
        process_jsons(today_str, country)
    client.close()