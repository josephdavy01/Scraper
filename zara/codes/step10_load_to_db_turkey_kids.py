import os
import json
import pymongo
import traceback
import pandas as pd
from datetime import date, datetime

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

# Function to get composition and origin of a product
def get_composition_make(json_data):
    try:
        result = {"composition": [], "origin": None}
        for section in json_data:
            if section["sectionType"] in ["materials", "certifiedMaterials", "recycledMaterials"]:
                for component in section["components"]:
                    if component["datatype"] in ["subtitle", "paragraph"]:
                        result['composition'].append(component["text"]["value"])
                        result['composition'].append('/n')
            elif section["sectionType"] == "origin":
                for component in section["components"]:
                    if component["datatype"] == "paragraph":
                        text = component["text"]["value"]
                        if "Made in" in text:
                            result["origin"] = text
        return result
    except:
        return None

def get_age_group(age_range):
    new_born_ages = ['0m', '1m', '2m', '3m', '4m', '5m', '6m']
    baby_ages = ['7m', '8m', '9m', '10m', '11m', '12m', '13m', '14m', '15m', '16m', '17m', '18m', '19m', '20m', '21m', '22m', '23m', '24m']
    junior_ages = ['2y', '3y', '4y', '5y', '6y', '7y']
    senior_ages = ['8y', '9y', '10y', '11y', '12y']
    teen_ages = ['13y', '14y', '15y', '16y', '17y']
    adult_ages = ['18y']

    age_goup_list = ['new_born', 'baby', 'junior', 'senior', 'teen', 'adult']

    if len(age_range) == 1:
        if age_range[0] in new_born_ages:
            return ['new_born']
        elif age_range[0] in baby_ages:
            return ['baby']
        elif age_range[0] in junior_ages:
            return ['junior']
        elif age_range[0] in senior_ages:
            return ['senior']
        elif age_range[0] in teen_ages:
            return ['teen']
        elif age_range[0] in adult_ages:
            return ['adult']
    else:
        age_group = []
        start = age_range[0]
        end = age_range[-1]

        if start in new_born_ages:
            sindex = age_goup_list.index('new_born')
        elif start in baby_ages:
            sindex = age_goup_list.index('baby')
        elif start in junior_ages:
            sindex = age_goup_list.index('junior')
        elif start in senior_ages:
            sindex = age_goup_list.index('senior')
        elif start in teen_ages:
            sindex = age_goup_list.index('teen')
        elif start in adult_ages:
            sindex = age_goup_list.index('adult')
        
        if end in new_born_ages:
            eindex = age_goup_list.index('new_born')
        elif end in baby_ages:
            eindex = age_goup_list.index('baby')
        elif end in junior_ages:
            eindex = age_goup_list.index('junior')
        elif end in senior_ages:
            eindex = age_goup_list.index('senior')
        elif end in teen_ages:
            eindex = age_goup_list.index('teen')
        elif end in adult_ages:
            eindex = age_goup_list.index('adult')

        for i in range(sindex, eindex + 1):
            age_group.append(age_goup_list[i])

        if age_group == []:
            age_group = ['others']
            
        return age_group

def remap_age_range(age_range):
    if len(age_range) > 1:
        age_range = [age_range[0], age_range[-1]]

    if len(age_range) > 1 and age_range[-1] == '1y':
        if 'm' in age_range[0]:
            start = age_range[0]
            age_range = [start, '12m']
        if 'y' in age_range[0]:
            age_range = ['0m', '12m']

    if age_range[0] == '1y':
        if len(age_range) == 1:
            age_range = ['12m']
        else:
            end = age_range[-1]
            age_range = ['12m', end]

    if len(age_range) > 1 and age_range[-1] == '2y':
        end = '24m'
        age_range = ['12m', end]

    return age_range

def get_age_range(age_shortname):
    age_range = []
    if 'year' in age_shortname:
        age_shortname = age_shortname.split('y')[0] + 'y'
    elif 'month' in age_shortname:
        age_shortname = age_shortname.split('m')[0] + 'm'

    if '1½ y' in age_shortname:
        age_shortname = age_shortname.replace('1½ y', '18 m')
        
    my = age_shortname.split(' ')[-1]
    numbers = age_shortname.split(' ')[0]

    if my == numbers:
        my = 'y'

    if '-' in numbers:
        n1 = int(numbers.split('-')[0])
        n2 = int(numbers.split('-')[1])
        for n in range(n1, n2+1):
            age_range.append(str(n) + my)
    elif '/' in numbers:
        n1 = int(numbers.split('/')[0])
        n2 = int(numbers.split('/')[1])
        for n in range(n1, n2+1):
            age_range.append(str(n) + my)
    else:
        age_range.append(numbers + my)

    age_range = remap_age_range(age_range)
    return age_range
    
# Function to create individual JSON objects for each SKU
def create_individual_json(json_data, fetch_date, category, composition_path):
    all_products = []
    product = json_data["product"]

    non_clothing_keywords = [
        # Footwear
        "BAMBAS", "BAÑO/CHANCLA", "BOTA", "BOTA PLANA", "BOTA TACON", "BOTIN",
        "BOTIN PLANO", "BOTIN TACON", "CALZADO DEPORTIVO", "CUÑA", "DEPORTIVO",
        "DEPORTIVO BOTIN", "SANDALIA", "SANDALIA DEPORTIVA", "SANDALIA E",
        "ZAPATO", "ZAPATO PLANO", "ZAPATO TACON",

        # Home & Decor
        "ALFOMBRAS", "ALFOMBRAS BAÑO", "CESTAS", "COLCHAS", "COLGADORES",
        "CRISTALERIA", "EDREDON", "HOME", "ILUMINACION", "INTERIORES",
        "JABON", "JARRONES", "MANTAS", "MANTELERIA", "MENAJE",
        "SABANAS/FUNDAS", "TOALLAS", "VELA AROMATICA",

        # Cosmetics & Personal Care
        "ACEITE CORPORAL", "AMBIENTADOR", "BALSAMO LABIAL", "CHAMPU",
        "CREMA HIDRATANTE", "CREMA MANOS", "COSMETICA PELO", "COSMETICOS UÑAS",
        "EAU DE COLOGNE", "EAU DE PERFUME", "EAU DE TOILETTE", "LOCION CORPORAL",
        "MAQUILL.LABIOS", "MAQUILLAJE FACIAL", "MAQUILLAJE OJOS", "ESMALTE DE UÑAS",
        "PERFUME",

        # Accessories
        "ACCESORIOS", "ACCESORIOS DECORAC", "ACCESORIOS MESA", "BILLETERAS",
        "BISUTERIA", "BOLSAS Y MOCHILAS", "BOLSOS", "CINTURONES", "CORBATAS",
        "MONEDERO BILLETERA", "PAÑOLETAS/FOULARD", "GAFAS", "GUANTE", "GORRO",

        # Stationery & Leisure
        "ART. PAPELERIA", "LIBRERIA", "PAPELERIA", "JUGUETES", "OCIO Y DEPORTE", "RUNNING",

        # Baby Gear & Furniture
        "MOBILIARIO NIÑO", "PELUCHES",

        # Misc
        "LLUVIA", "PALA/PINKY", "TOPS Y OTRAS P.", "No Title"
        ]

    family_name = product['familyName']
    if family_name.upper() in non_clothing_keywords:
        print(f"Skipping non-clothing item with family name: {family_name}")
        return all_products
    
    product_url = (json_data['productMetaData'][0]['url'])
    product_name = product["name"].lower()
    detail = product["detail"]
    reference_code = detail["reference"]
    product_id = 'zar' + reference_code.split('-')[0]
    colors = detail["colors"]

    if 'boy' in category:
        gender = 'male'
    elif 'girl' in category:
        gender = 'female'
    else:
        gender = 'unisex'

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

            if os.path.exists(f'{composition_path}/{color_product_id}.json'):
                with open(f'{composition_path}/{color_product_id}.json', 'r', encoding='utf-8') as json_file:
                    data = json.load(json_file)
                co_data = get_composition_make(data)
                if co_data:
                    product_composition = "\n".join(co_data['composition'])
                    if co_data['origin'] and "Made in" in co_data['origin']:
                        product_origin = co_data['origin'].split("Made in ")[-1].lower()
                    else:
                        product_origin = co_data['origin']
                else:
                    product_composition = None
                    product_origin = None
            else:
                product_composition = None
                product_origin = None

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
                if '(' in size_name:
                    age_shortname = size_name.split('(')[0].strip()
                    if 'months' in age_shortname or 'years' in age_shortname:
                        age_range = get_age_range(age_shortname)
                        age_group = get_age_group(age_range)

                        size_reference_code = size["reference"]
                        sku = size["sku"]
                        availability = size["availability"]
                        size_price = size["price"]
                        if not size_price  or size_price  == 0:
                            continue
                        size_old_price = size.get("oldPrice", size_price)
                        if size_old_price == 0 or size_old_price == None:
                            size_old_price = size_price
                        demand = size["demand"]

                        entry = {
                            "product_id": product_id,
                            "gender": gender,
                            "age_group": age_group,
                            "age_range": age_range,
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
                            "demand": demand,
                            "composition": product_composition,
                            "origin": product_origin,
                            "images": images
                        }
                        all_products.append(entry)
    return all_products

# Function to process a folder and log SKU details
def process_folder(root_path, fetch_date, composition_path, specific_folders=None):
    categories_path = os.path.join(root_path, "Json_data")
    categories = specific_folders if specific_folders else get_subfolder_names(categories_path)
    
    for category in categories:
        category_path = os.path.join(categories_path, category)
        subcategories = get_subfolder_names(category_path, [])
        
        for subcategory in subcategories:
            subcategory_path = os.path.join(category_path, subcategory)
            file_paths = get_file_paths_in_folder(subcategory_path)
            
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                if not filename.startswith('-p'):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as json_file:
                            data = json.load(json_file)
                            skus = create_individual_json(data, fetch_date, category, composition_path)
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
    
    geography = "Turkey"
    db = client['tg_analytics']
    collection = db[f'crawler_sink_zara_{geography.lower()}_kids']
    
    today = date.today()
    fetch_date =today.strftime('%Y-%m-%d')

    composition_path = f'{geography}/Extra_details_data'
    specific_folders = ['KIDS']
    root_path = rf"{geography}/Data/{fetch_date}"
    
    # Process folder and log SKU details
    process_folder(root_path, fetch_date, composition_path, specific_folders)

    client.close()