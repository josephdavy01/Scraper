import os
import json
import traceback
import pandas as pd
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
    if gender in ['men', 'boys', 'mens', 'mens;']:
        return 'male'
    elif gender in ['women', 'girls', 'womens', 'womens;']:
        return 'female'
    else:
        return 'unisex'

def datetime_serializer(obj):
    """Custom JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def get_images(ccode, productCarousel):
    for i in productCarousel:
        if i['color']['code'] == ccode:
            images = []
            for j in i['imageInfo']:
                temp = {
                    "url": j,
                    "image_style": 's0'
                }
                images.append(temp)
            return images

def get_composition(ccode, colorAttributes):
    for i in colorAttributes:
        if i['colorId'] == ccode:
            description = i['wwmt']
            for j in i['careAndContent']['sections']:
                if j['title'] == 'Materials':
                    composition = ''
                    for k in j['attributes']:
                        composition += k['list']['title'] + ': ' + ', '.join(k['list']['items']) + '; '
            return description, composition.strip()

def process_product_data(base_url, fetch_date, json_data, gender):
    products = []
    category = json_data['allLocalePids']['categoryUnifiedId'].lower()
    cat_type = category.split('-')[-1]

    if cat_type in ("accessories","hair-accessories","bags","gloves-mittens","equipment","hats","scarves-wraps","yoga-mats","water-bottles","shoes","shoe""face-masks",
    "keychains","hair-tools","travel-accessories","training-accessories","running-accessories","belt-bags","duffle-bags","backpacks"):
        return products
    
    gender = remap_gender(gender.lower())
    name = json_data['productSummary']['displayName'].lower()
    pid = 'lul' + json_data['productSummary']['productId'][4:]

    colorAttributes = json_data['colorAttributes']
    productCarousel = json_data['productCarousel']
    skus = json_data['skus']
    
    for sku_data in skus:
        sku = sku_data['id']
        size = sku_data['size']
        oldprice = float(sku_data['price']['listPrice'])
        price = float(sku_data['price']['salePrice']) if sku_data['price']['salePrice'] else oldprice
        if  not price or price == 0:
            continue
        color = sku_data['color']['name'].lower()
        colorcode = sku_data['color']['code']
        colorreference = sku_data['styleId']
        productreference = sku_data['styleNumber']
        
        description, composition = get_composition(colorcode, colorAttributes)
        images = get_images(colorcode, productCarousel)
        availability = 'in_stock' if sku_data['available'] else 'out_of_stock'
        url = f"{base_url}{sku_data['skuUrl'].split('?')[0]}?color={colorcode}"
        
        product = {
            "product_id": pid,
            "gender": gender,
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(fetch_date),
            "url": url,
            "title": name,
            "description": description,
            "product_ref_code": productreference,
            "color_id": f'{pid}%{colorcode}',
            "color_name": color,
            "color_ref_code": colorreference,
            "sku": f'{pid}%{sku}',
            "size_name": size,
            "size_ref_code": None,
            "price": price,
            "launch_price": oldprice,
            "availability": availability,
            "demand": None,
            "composition": composition,
            "origin": None,
            "images": images
        }
        products.append(product)
    return products

def get_folders(sub_folders, exclude_folder=None):
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder] if exclude_folder else folders
    return [folder for folder in folders if '.json' not in folder]

def process_and_save_to_json(base_url, fetch_date, country):
    all_products = []
    log_data = []
    gender_folder = os.path.join(country, fetch_date, 'Json_data')
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
                    
                    products = process_product_data(base_url, fetch_date, data, gender)
                    all_products.extend(products)
                    
                    for product in products:
                        print(f'Processed: {product["product_id"]}, SKU: {product["sku"]}')
                        log_data.append({
                            "file_path": file_path,
                            "sku": product["sku"],
                            "status": 'processed'
                        })
                
                except Exception as e:
                    print(f"Error processing {file_path}: {str(e)}")
                    traceback.print_exc()
                    log_data.append({
                        "file_path": file_path,
                        "error": str(e),
                        "status": 'failed'
                    })
                    #log the error to a log file
                    with open(f'{country}\{fetch_date}\Data\error_log.txt', 'a', encoding='utf-8') as log_file:
                        log_file.write(f"Error processing {file_path}: {str(e)}\n")
                        log_file.write(traceback.format_exc() + '\n')
    
    # Save all products to a single JSON file
    output_file = os.path.join(country, fetch_date, 'Data', f'products_data_{country}.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False,  default=datetime_serializer)
    print(f'\nAll products saved to {output_file}')
    
    # Save processing log
    log_file = os.path.join(country, fetch_date, 'Validation', f'sku_log_{fetch_date}.csv')
    pd.DataFrame(log_data).to_csv(log_file, index=False)
    print(f'SKU log saved to {log_file}')

def upload_to_json(countries, fetch_date, re_run=False):   
    for country, base_url in countries.items():
        # Ensure the directory structure exists
        # Check file existence of products_data
        data_file = os.path.join(country, fetch_date, 'Data', f'products_data_{country}.json')
        if not re_run and os.path.exists(data_file):
            print(f"Data file {data_file} already exists. Skipping processing for {country}.")
            continue
        os.makedirs(os.path.join(country, fetch_date, 'Data'), exist_ok=True)
        print(f"\nProcessing data for {country}...")
        process_and_save_to_json(base_url, fetch_date, country)
    
    print("\nData processing completed for all countries.")

if __name__ == "__main__":
    TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
    # TODAY_DATE = "2025-11-18"
    TODAY_DATE_OBJ = datetime.strptime(TODAY_DATE, "%Y-%m-%d")
    TODAY = TODAY_DATE_OBJ.strftime("%A")

    COUNTRIES = {
        'Canada': 'https://shop.lululemon.com/en-ca/',
        'USA': 'https://shop.lululemon.com/'
    }

    # Configuration
    CONFIG = {
        'USA': {
            'base_url': 'https://shop.lululemon.com',
            'browsers': 2,
            'data_dir': 'USA'
        },
        'Canada': {
            'base_url': 'https://shop.lululemon.com/en-ca',
            'browsers': 2,
            'data_dir': 'Canada'
        }
    }
    upload_to_json(COUNTRIES,TODAY_DATE)