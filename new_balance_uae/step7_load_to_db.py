import os
import re
import json
import math
import pymongo
import traceback
import html as html_module
from bs4 import BeautifulSoup
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

def calculate_original_price(price, badge_text):
    if not badge_text:
        return price
    
    badge_lower = badge_text.lower().strip()
    if 'reduced' in badge_lower:
        number_match = re.search(r'(\d+)', badge_lower)
        
        if number_match:
            discount_percentage = float(number_match.group(1))
            if discount_percentage >= 100:
                return price
            launch_price = price / (1 - discount_percentage/100)
            return math.ceil(launch_price / 5) * 5
        else:
            return price
    return price

def extract_weight_from_features(key_features):
    if not key_features:
        return None
    
    for feature in key_features:
        feature_lower = feature.lower()
        weight_match = re.search(r'weight[:\s]*(\d+(?:\.\d+)?)\s*g', feature_lower)
        if weight_match:
            return f"{weight_match.group(1)}g" 
    return None
    
def clean_product_name(product_name):
    if not product_name:
        return product_name
    name = product_name.strip()
    prefixes_to_remove = ["men's ", "women's ", "mens ", "womens ", "Women's", "Men's "]
    
    for prefix in prefixes_to_remove:
        if name.lower().startswith(prefix.lower()):
            return name[len(prefix):].strip()
    
    return name

def is_apparel(json_data):
    """Check if product is apparel based on apparel sizes (XS, S, M, L, XL, XXL, etc.)."""
    apparel_sizes = {"xxs", "xs", "s", "m", "l", "xl", "xxl", "xxxl"}
    sizes = []
    for size_key in ['US']:
        if json_data.get('Sizes', {}).get(size_key):
            sizes = json_data.get('Sizes', {}).get(size_key, [])
            break

    for size_info in sizes:
        if isinstance(size_info, dict):
            size_name = size_info.get('name', '').strip().lower()
            if size_name in apparel_sizes:
                return True  # Apparel size found
    return False  # No apparel sizes found

def extract_heel_to_toe_drop(quick_facts):
    if not quick_facts or not isinstance(quick_facts, dict):
        return None
    heel_drop = quick_facts.get('heel_to_toe_drop')
    if heel_drop:
        return str(heel_drop)
    for key in quick_facts.keys():
        if 'heel' in key.lower() and 'drop' in key.lower():
            return str(quick_facts[key])
    return None

def extract_upper_material(material_data):
    if not material_data:
        return None
    
    if isinstance(material_data, dict):
        materials = material_data.get('materials', [])
        if materials and isinstance(materials, list):
            return '; '.join(materials)
        return None
    elif isinstance(material_data, str):
        return material_data
    return None

def extract_origin(material_data):
    if not material_data or not isinstance(material_data, dict):
        return None
    supplier = material_data.get('supplier')
    if supplier:
        if ',' in supplier:
            parts = supplier.split(',')
            return parts[-1].strip()
        return supplier.strip()
    return None

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

def clean_size_name(size_name):
    if not size_name:
        return ""
    size = size_name
    for pattern in ['Only', 'No items', 'Notify me']:
        size = size.split(pattern)[0]
    
    return size.strip()

def get_image_style(images):
    image_list = []
    for image in images:
        temp = {
            "url": image,
            "image_style": 's0'
        }
        image_list.append(temp)

    return image_list

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

def create_individual_json(today_str, json_data, file_gender):
    all_products = []
    
    if not json_data or not isinstance(json_data, dict):
        print(f"Skipping: Invalid or empty JSON data: {json_data}")
        return []
    
    if not is_apparel(json_data):
        return []
    
    name = clean_product_name(json_data.get('Product Name', '')).lower()
    product_id = f'nbl'+ json_data.get('SKU', '').split('-')[0].strip()
    url = json_data.get('Product Url', '') or json_data.get('Original Product Url', '')
    
    # Combine category and subcategory for gender detection
    subcategory = json_data.get('Subcategory', '').lower()
    
    print(f"Debug: Subcategory='{subcategory}', File Gender='{file_gender}'")
    
    if 'unisex' in subcategory:
        gender = 'unisex'
    elif 'women' in subcategory:
        gender = 'female'
    elif 'men' in subcategory:
        gender = 'male'
    elif 'kids' in subcategory:
        gender = 'kids'
    else:
        gender = 'unisex'
    
    print(f"Debug: Assigned gender='{gender}'")
        
    description = json_data.get('Description', '')
    price_str = json_data.get('Launch Price', '0')
    sku = json_data.get('SKU', '')
    # Clean the string
    price_str = price_str.replace('AED', '').replace('\xa0', '').replace(',', '').strip()
    # Convert to float
    launch_price = float(price_str)
    material_data = json_data.get('material')
    composition = extract_upper_material(material_data)
    origin_raw = extract_origin(material_data)
    origin = origin_raw.lower() if origin_raw else None
    try:
        price = float(json_data.get('Price', '0').replace('AED ', ''))
    except (ValueError, TypeError):
        price = 0.0
    key_features = json_data.get('key_features', [])
    if key_features:
        description += '\n' + ' | '.join(key_features)

    description = extract_text_from_html(description)
    quick_facts = json_data.get('quick_facts', {})
    
    # Process main product sizes
    main_images = json_data.get('Images', [])
    cid = main_images[0].split('/')[-1].split('_')[0].split('-')[-1] if main_images else ''
    color_name = json_data.get('Color Name', '').strip().lower()
    for size_key in ['US']:
        sizes = json_data.get('Sizes', {}).get(size_key, [])
        if not sizes:
            continue
        
        for size_info in sizes:
            if not isinstance(size_info, dict):
                print(f"Skipping invalid size info for {size_key}: {size_info}")
                continue
                
            size_name = size_info.get('name')
            size_availability = size_info.get('available', True)
            
            size = clean_size_name(size_name)
            if not size:
                print(f"Skipping empty size name for {size_key}: {size_name}")
                continue
                
            size_specific_sku = f'{product_id}%p{product_id.replace('nbl', '')}c{cid}s{size}'.replace(' ', '')
            availability = 'in_stock' if size_availability else 'out_of_stock'
            images = get_image_style(main_images)
            
            # Skip products that mention "socks" in the title or description
            if 'socks' in name or 'socks' in description.lower():
                print(f"Skipping product with socks: {name}")
                continue

            entry = {
                "product_id": product_id,
                "gender": gender,
                "age_group": get_age_group(gender),
                "age_range": get_age_range(gender),
                "date_of_scraping": parse_launch_date(today_str),
                "url": url,
                "title": name,
                "description": description,
                "product_ref_code": None,
                "color_id": f'{product_id}%{cid}',
                "color_name": color_name,
                "color_ref_code": cid,
                "sku_as_per_website": sku,
                "sku": size_specific_sku,
                "size_name": size,
                "size_ref_code": size_info.get('reference_code'),
                "price": price,
                "launch_price": launch_price,
                "availability": availability,
                "demand": None,
                "composition": composition,
                "made_in": None,
                "images": images
            }
            all_products.append(entry)
    
    # Process variants
    variants = json_data.get('Variants', [])
    for variant in variants:
        variant_color_name = variant.get('Color Name', '').strip().lower()
        variant_images = variant.get('Images', [])
        variant_cid = variant_images[0].split('/')[-1].split('_')[0].split('-')[-1] if variant_images else cid
        try:
            variant_price = float(variant.get('Price', '0').replace('AED ', ''))
        except (ValueError, TypeError):
            variant_price = 0.0
        
        for size_key in ['US']:
            variant_sizes = variant.get('Sizes', {}).get(size_key, [])
            if not variant_sizes:
                continue
            
            for size_info in variant_sizes:
                if not isinstance(size_info, dict):
                    print(f"Skipping invalid size info in variant {variant_color_name} for {size_key}: {size_info}")
                    continue
                    
                size_name = size_info.get('name')
                if size_name:
                    size_name = f'{size_name}'
                size_availability = size_info.get('available', True)
                
                size = clean_size_name(size_name)
                if not size:
                    print(f"Skipping empty size name in variant {variant_color_name} for {size_key}: {size_name}")
                    continue
                    
                size_specific_sku = f'{product_id}%p{product_id.replace('nbl', '')}c{variant_cid}s{size}'.replace(' ', '')
                availability = 'in_stock' if size_availability else 'out_of_stock'
                images = get_image_style(variant_images)
                
                entry = {
                    "product_id": product_id,
                    "gender": gender,
                    "age_group": get_age_group(gender),
                    "age_range": get_age_range(gender),
                    "date_of_scraping": parse_launch_date(today_str),
                    "url": url,
                    "title": name,
                    "description": description,
                    "product_ref_code": None,
                    "color_id": f'{product_id}%{variant_cid}',
                    "color_name": variant_color_name,
                    "color_ref_code": variant_cid,
                    "sku_as_per_website": sku,
                    "sku": size_specific_sku,
                    "size_name": size,  # Fixed: Use cleaned size name instead of variant_sizes
                    "size_ref_code": size_info.get('reference_code'),
                    "price": variant_price,
                    "launch_price": launch_price,
                    "availability": availability,
                    "demand": None,
                    "composition": composition,
                    "made_in": None,
                    "images": images
                }
                all_products.append(entry)
    return all_products

def process_jsons(today_str, country, collection):
    gender_folder = os.path.join(country, 'data', today_str, 'json_data')
    genders = os.listdir(gender_folder)
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = os.listdir(category_folder)
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
                        print(f"Skipping {file_path} - not apparel or missing data")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = "2025-12-06" 
    
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    
    countries = ['UAE']

    for country in countries:
        collection = db[f'crawler_sink_newbalance_{country.lower()}']
        print(f"Processing {country} footwaear...")
        process_jsons(today_str, country, collection)
        print(f"Footware data loading for {country} completed!")
        
    client.close()