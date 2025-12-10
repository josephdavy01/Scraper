import os
import re
import json
import pymongo
import traceback
from datetime import date, datetime


def get_product_text(j):
    meta_data = j.get('meta_data', {})  # Ensure it's a dict
    data_attributes = j.get('data_attributes', {})
    return f"{meta_data.get('property_og:title', '')} {j.get('title', '')} {data_attributes.get('data-product-type', '')} {' '.join(j.get('breadcrumbs', []))}".lower().strip()


def is_apparel(j):
    keywords = ("apparel",)
    text = get_product_text(j)
    return any(k in text for k in keywords)


def map_base_sku(all_sizes_data, target_size):
    for size_obj in all_sizes_data:
        if size_obj.get("data-sizevalue") == target_size and size_obj.get("link_data-select") == "js-mens-size":
            base_sku = size_obj.get("link_data-product-size-id", "").split("ANA_")[-1]
            return base_sku
    return None
             
def format_images(image_list):
    temp_styles = []
    processed_urls = set()
    for img_url in image_list:
        cleaned_url = img_url.split('?')[0]
        if cleaned_url in processed_urls:
            continue
        processed_urls.add(cleaned_url)
        if '_FR_' in cleaned_url:
            image_style = "n_f_f_c"
        else:
            image_style = "s0"

        temp_styles.append({
            "url": cleaned_url,
            "image_style": image_style
        })
    return temp_styles


def extract_color_name_id(json_data):
    url = json_data.get('source_url', '')
    match = re.search(r"/([^/]+)\.html$", url)
    
    product_code = ''
    if match:
        product_code = match.group(1)

    color_id = ''
    product_id = ''
    if '-' in product_code:
        parts = product_code.split('-')
        product_ref_code=product_code.split("ANA_")[-1]
        product_id = parts[0].split("ANA_")[-1]
        color_id = parts[1]

    color_name = None
    color_variants = json_data.get('color_variants', [])
    for variant in color_variants:
        if variant.get('variation_group', '') == product_code:
            color_name = variant.get('color_alt')
            if color_name:
                break
    if not color_name:
        for variant in color_variants:
            if variant.get('aria_label', '').startswith('Color selected'):
                color_name = variant.get('color_alt')
                break
    if not color_name:
        title_parts = json_data.get('meta_data', {}).get('property_og:title', '').split('|')
        color_name = title_parts[3].strip() if len(title_parts) > 3 else None

    return color_name, product_code, color_id, product_id, url,product_ref_code


def get_age_group(gender):
    gender = gender.lower()
    if gender in ['female', 'women', 'male', 'men']:
        return ['adult']
    if gender in ['kids', 'youth']:
        return ['kids']
    return ['adult']


def get_age_range(gender):
    gender = gender.lower()
    if gender in ['female', 'women', 'male', 'men']:
        return ['18y']
    if gender in ['kids', 'youth']:
        return ['1y', '17y']
    return ['18y'] 


def gender_map(j):
    text = get_product_text(j)
    if any(keyword in text for keyword in ("unisex",)):
        return "unisex"
    elif any(keyword in text for keyword in ("kids", "kid", "children", "youth", "big kids", "junior")):
        return "kids"
    elif any(keyword in text for keyword in ("women", "women's", "womens", "female", "females")):
        return "female"
    elif any(keyword in text for keyword in ("men", "mens", "men's", "male", "males")):
        return "male"
    else:
        return "unisex"


def create_individual_json(today_str, json_data, gender):
    all_products = []
    if not json_data or not isinstance(json_data, dict):
        return []
    
    if not is_apparel(json_data):
        return []

    color_name, product_code, color_id, product_id, url,product_ref_code = extract_color_name_id(json_data)
    
    title = json_data.get('title', '').lower().strip()
    mapped_gender = gender_map(json_data)
    
    accordion_sections=json_data.get('accordion_sections')

    tech_section = accordion_sections.get('Tech & Materials', {})
    details_section = accordion_sections.get('Details', {})
    
    tech_content = tech_section.get('content', '')
    details_data = details_section.get('content', {})

    price_info = json_data.get('price_info', {})

    current_price_str = price_info.get('current_price', None)
    label = price_info.get('aria_label_price_info', None)
    aria_original_price_str = price_info.get('aria_original_price', None)

    current_price_str = current_price_str.replace('$', '').strip() if current_price_str else ''
    aria_original_price_str = aria_original_price_str.replace('$', '').strip() if aria_original_price_str else ''
    
    launch_price = 0.0
    price = 0.0

    try:
        price = float(current_price_str) if current_price_str else 0.0
        if label:
            launch_price = float(aria_original_price_str)
        else:
            launch_price = price
    except (ValueError, TypeError):
        launch_price = 0.0
        price = 0.0


    base_product_id = f'asi{product_id}'
    
    extraction_timestamp = json_data.get('extraction_timestamp', today_str)
    try:
        parsed_date = datetime.strptime(extraction_timestamp.split('T')[0], '%Y-%m-%d')
    except Exception:
        parsed_date = datetime.strptime(today_str, '%Y-%m-%d')

    raw_images = json_data.get('images', [])
    formatted_images = format_images(raw_images)

    size_stock = json_data.get('availability_info', {}).get('size_stock', {}) 
    all_sizes_data = json_data.get('sizes', [])

    for size, in_stock in size_stock.items():
        if not size:
            continue
        
        availability = "in_stock" if in_stock else "out_of_stock"
        
        base_sku = map_base_sku(all_sizes_data, size)
        if not base_sku:
            continue 

        size_specific_sku = f'{base_product_id}%{base_sku}' 
        
        entry = {
            "product_id": f"asi{product_id}",
            "gender": mapped_gender,
            "age_group": get_age_group(mapped_gender),
            "age_range": get_age_range(mapped_gender),
            "date_of_scraping": parsed_date,
            "url": url,
            "title": title,
            "description": details_data,
            "product_ref_code": product_ref_code,
            "color_id": f'{base_product_id}%{color_id}',
            "color_name": color_name.lower().strip() if color_name else None,
            "color_ref_code": product_ref_code,
            "sku": size_specific_sku,
            "size_name": f"US {size}",
            "size_ref_code": None,
            "price": price,
            "launch_price": launch_price,
            "availability": availability,
            "demand":None,
            "composition":tech_content,
            "origin": None,
            "images": formatted_images,
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


def process_jsons(today_str, country, collection):
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
                        print(f"Skipping {file} - not apparel or missing data")
                    
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()


if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    
    countries = ['USA']


    for country in countries:
        collection = db[f'crawler_sink_asics_{country.lower()}']
        print(f"Processing {country} apparel...")
        process_jsons(today_str, country, collection)
        print(f"Apparel data loading for {country} completed!")
        
    client.close()
