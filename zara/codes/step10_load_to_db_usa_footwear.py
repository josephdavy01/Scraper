import os
import json
import pymongo
import traceback
import pandas as pd
from datetime import date, datetime

# Function to get names of subfolders in a folder, excluding specified folders
def get_subfolder_names(folder_path, exclude_folders=None):
    exclude_folders = exclude_folders if exclude_folders else []
    return [f.name for f in os.scandir(folder_path) if f.is_dir() and f.name not in exclude_folders]

# Function to get file paths in a folder
def get_file_paths_in_folder(folder_path):
    return [os.path.join(folder_path, file) for file in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, file))]

# Function to get the style of an image based on its filename
def get_image_style(filename):
    try:
        if '_' in filename:
            code = filename.split('_', 1)[1]
            data = {
                "1_1_1": "m_f_f_c",
                "2_1_1": "s2",
                "2_2_1": "s3",
                "2_3_1": "s4",
                "2_4_1": "s5",
                "2_5_1": "s6",
                "2_6_1": "s7",
                "2_7_1": "s8",
                "6_1_1": "n_f_f_c",
                "6_2_1": "s10",
                "6_3_1": "s11",
                "6_4_1": "s12",
                "6_5_1": "s13",
                "6_6_1": "s14",
                "6_7_1": "s15",
                "6_8_1": "s16",
                "6_9_1": "s17"
            }
            return data.get(code, 's0')
        elif '-' in filename:
            code = filename.split('-')[-1]
            if code == 'e1':
                return 'n_f_f_c'
            else:
                return 's0'
    except:
        return 's0'

# Function to get composition of a product
def get_composition(json_data):
    def format_comps(components):
        formatted = ', '.join(f" {c.get('percentage', '')} {c.get('material', '')} ".strip() for c in components)
        return formatted if formatted.strip() else None

    # Initialize all composition variables as None
    upper = None
    lining = None
    sole = None
    insole = None
    
    try:
        # Get the composition details from the product
        product_detail = json_data.get('product', {}).get('detail', {})
        
        # First try to get from detailedComposition
        json_composition = product_detail.get('detailedComposition', {})
        if json_composition and 'parts' in json_composition:
            for part in json_composition.get('parts', []):
                desc = part.get('description', '').upper()
                if part.get('components'):
                    value = format_comps(part['components'])
                    if value:  # Only assign if we have a non-empty value
                        if desc == 'UPPER':
                            upper = value
                        elif desc == 'LINING':
                            lining = value
                        elif desc == 'SOLE':
                            sole = value
                        elif desc == 'INSOLE':
                            insole = value
        
        # If no detailed composition, try getting from composition field
        if not any([upper, lining, sole, insole]):
            composition = product_detail.get('composition', '')
            if composition:
                # Try to parse the composition text
                comp_lower = composition.lower()
                if 'upper:' in comp_lower:
                    upper = composition.split('upper:', 1)[1].split('.')[0].strip()
                if 'sole:' in comp_lower:
                    sole = composition.split('sole:', 1)[1].split('.')[0].strip()
                if 'lining:' in comp_lower:
                    lining = composition.split('lining:', 1)[1].split('.')[0].strip()
                if 'insole:' in comp_lower:
                    insole = composition.split('insole:', 1)[1].split('.')[0].strip()

    except Exception as e:
        print(f"Error parsing composition: {str(e)}")
        return None, None, None, None

    return upper, lining, sole, insole

def parse_launch_date(date_string):
    format_string_with_ms = '%Y-%m-%dT%H:%M:%S.%fZ'
    format_string_without_ms = '%Y-%m-%dT%H:%M:%SZ'
    format_string_date_only = '%Y-%m-%d'
    format_string_with_ms_no_tz = '%Y-%m-%d %H:%M:%S.%f'
    
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            try:
                return datetime.strptime(date_string, format_string_date_only)
            except ValueError:
                return datetime.strptime(date_string, format_string_with_ms_no_tz)

def remap_gender(gender):
    gender = gender.strip().lower()
    male_terms = ["male", "m", "man", "boy", "gentleman"]
    female_terms = ["female", "f", "woman", "girl", "lady", "kid"]
    unisex_terms = ["unisex", "both", "all", "non-binary", "gender-neutral", "universal", "unknown"]

    if gender in male_terms:
        return "male"
    elif gender in female_terms:
        return "female"
    elif gender in unisex_terms:
        return "unisex"
    else:
        return "unisex"
    
# Function to create individual JSON objects for each SKU
def create_individual_json(file_name, json_data, fetch_date, composition_path):
    all_products = []
    product = json_data["product"]

    footwear_keywords = [
        # Footwear
        "BAMBAS", "BAÑO/CHANCLA", "BOTA", "BOTA PLANA", "BOTA TACON", "BOTIN",
        "BOTIN PLANO", "BOTIN TACON", "CALZADO DEPORTIVO", "CUÑA", "DEPORTIVO",
        "DEPORTIVO BOTIN", "SANDALIA", "SANDALIA DEPORTIVA", "SANDALIA E",
        "ZAPATO", "ZAPATO PLANO", "ZAPATO TACON"
        ]

    family_name = product['familyName']
    if family_name.upper() not in footwear_keywords:
        print(f"Skipping non-footwear item with family name: {family_name}")
        return all_products
    
    file_name = file_name.split("_")[0]
    product_url = (json_data['productMetaData'][0]['url'])
    product_id = 'zar' + str(((file_name.split('-')[-1]).split('_')[0]).replace('.json', '').replace('p', ''))
    product_name = product["name"].lower()
    gender = remap_gender(product["sectionName"])
    detail = product["detail"]
    reference_code = detail["reference"]
    colors = detail["colors"]
    for index, color in enumerate(colors):
        color_name = color["name"].lower().strip()
        if color_name == '':
            color_name = None
        if color_name:
            color_id = color["id"]
            color_hex_code = color["hexCode"]
            if color_hex_code == '':
                color_hex_code = '#others'
            color_product_id = color["productId"]
            
            upper_material, lining_material, sole_material, insole_material = get_composition(json_data)

            color_reference_code = color["reference"]
            description = color["description"]
            if description == '':
                description = None
            main_images = color["mainImgs"]
            images = [
                {
                    "url": 'https://static.zara.net/photos//' + img["path"] + "/w/" + str(img['width']) + '/' + img["name"] + ".jpg?ts=" + img["timestamp"],
                    "image_style": get_image_style(img['name']),
                } for img in main_images
            ]
            sizes = color["sizes"]
            for size in sizes:
                size_name = size["name"]
                sku = size["sku"]
                availability = size["availability"]
                size_price = size["price"]
                size_old_price = size.get("oldPrice", None)
                if size_old_price == 0 or size_old_price == None:
                    size_old_price = size_price
                size_reference_code = size["reference"]
                demand = size["demand"]

                json_data = {
                    "product_id": product_id,
                    "sub_brand": None,
                    "gender": gender,
                    "age_group": ['adult'],
                    "age_range": ['18y'],
                    "date_of_scraping": parse_launch_date(fetch_date),
                    "url": product_url,
                    "title": product_name,
                    "description": description,
                    "product_ref_code" : reference_code,
                    "color_id": f'{product_id}%{color_id}',
                    "color_name": color_name,
                    "color_ref_code" : color_reference_code,
                    "sku": f'{product_id}%{sku}',
                    "size_name": size_name,
                    "size_ref_code" : size_reference_code,
                    "price": float(size_price)/100,
                    "launch_price": float(size_old_price)/100,
                    "availability": availability,
                    "sole_material": sole_material,
                    "upper_material": upper_material,
                    "closure_type": None,
                    "toe_type": None,
                    "heel_type": None,
                    "weight": None,
                    "heel_to_toe_drop": None,
                    "occasion": None,
                    "origin": None,
                    "images": images
                }
                all_products.append(json_data)
    return all_products

# Function to process a folder and log SKU details
def process_folder(root_path, fetch_date, composition_path, specific_folders=None):
    categories_path = os.path.join(root_path, "Json_data")
    categories = specific_folders if specific_folders else get_subfolder_names(categories_path)
    
    for category in categories:
        category_path = os.path.join(categories_path, category)
        subcategories = get_subfolder_names(category_path, ['_new','best_sellers', 'curated_at_home', 'gift_cards', 
                                                            'special_prices', 'linen', 'perfumes', 'beauty', 
                                                            'accessories', 'bags&backpacks', 'matching_sets', 'made_in_india', 
                                                            'accessories&jewellery', 'accessories&jewelry', 'bags', 'co-ord_sets',
                                                            'makeup', 'edited&personalized', 'events', 'fragrances', 'studio-collection',
                                                            '90Â´s-archive', 'into-the-process', 'accessories-&-jewelry', 'zara-hair',
                                                            'accessories-&-jewellery', 'trainers', 'bags-&-backpacks'])
        
        for subcategory in subcategories:
            subcategory_path = os.path.join(category_path, subcategory)
            file_paths = get_file_paths_in_folder(subcategory_path)
            
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                if not filename.startswith('-p'):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as json_file:
                            data = json.load(json_file)
                            skus = create_individual_json(filename, data, fetch_date, composition_path)
                            print(file_path)
                            # collection.insert_many(skus)
                            for sku in skus:
                                print(f'Inserting Product id: {sku["product_id"]}, SKU: {sku["sku"]}')
                                collection.insert_one(sku)
                    except Exception as e:
                        print(e)
                        traceback.print_exc()

# Function to get product IDs from a JSON file
def get_pids_from_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

if __name__ == "__main__":
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    
    geography = "USA"
    db = client['tg_analytics']
    collection = db[f'crawler_sink_zara_{geography.lower()}_footwear']
    
    today = date.today()
    fetch_date = today.strftime('%Y-%m-%d')
    # fetch_date='2025-10-04'

    composition_path = f'{geography}/Extra_details_data'
    root_path = rf"{geography}/Data/{fetch_date}"
    specific_folders = ['WOMAN', 'MAN']

    # Process folder and log SKU details
    process_folder(root_path, fetch_date, composition_path, specific_folders)

    client.close()