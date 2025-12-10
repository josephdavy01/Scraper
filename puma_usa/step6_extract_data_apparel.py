import os
import json
import traceback
import pandas as pd
from datetime import date, datetime
import re

kids_size_to_age_map = {
    # Infant + Toddler Sizes
    "0/3M": "0-3 m",
    "3/6M": "3-6 m",
    "6/9M": "6-9 m",
    "12M": "9-12 m",
    "18M": "12-18 m",
    "2T": "1-2 y",
    "3T": "2-3 y",
    "4T": "3-4 y",

    # Little Kids' Sizes
    "5": "4-5 y",
    "6": "5-6 y",
    "XS": "6-8 y",

    # Junior Sizes
    "S": "8-9 y",
    "M": "10-12 y",
    "L": "13-14 y",
    "XL": "15-16 y"
}

age_code_to_category_map = {
    "0-6 M": "New Born",
    "6-24 M": "Baby",
    "2-8 Y": "Junior",
    "8-12 Y": "Senior",
    "13-17 Y": "Teen"
}

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
        
def determine_gender(primary_category_id, size_chart_id):
    """
    Determines a gender category based on keywords in string identifiers.

    It checks fields in a specific order of priority:
    1. primaryCategoryId
    2. sizeChartId

    Args:
        primary_category_id (str): The value from the 'primaryCategoryId' field.
        size_chart_id (str): The value from the 'sizeChartId' field.

    Returns:
        str: The determined gender ('male', 'female', 'kids', 'unisex').
    """
    
    # Helper function to perform the keyword check on a single string
    def check_string(input_string):
        if not input_string:
            return None
            
        text = input_string.lower()  # Make the check case-insensitive
        
        if 'women' in text or 'womens' in text:
            return 'female'
        if 'men' in text or 'mens' in text:
            return 'male'
        if 'kid' in text or 'kids' in text:
            return 'kids'
        if 'unisex' in text:
            return 'unisex'
            
        return None

    # 1. Check primaryCategoryId with highest priority
    gender = check_string(primary_category_id)
    if gender:
        return gender

    # 2. If nothing was found, check sizeChartId
    gender = check_string(size_chart_id)
    if gender:
        return gender

    # 3. If no keywords are found in any priority field, default to 'unisex'
    return 'unisex'

def determine_kids_gender(name):
    """
    Determines a gender category based on keywords in string identifiers.

    It checks fields in a specific order of priority:
    1. name

    Returns:
        str: The determined gender ('boys', 'girls', 'unisex').
    """
    
    # Helper function to perform the keyword check on a single string
    def check_string(input_string):
        if not input_string:
            return None
            
        text = input_string.lower()  # Make the check case-insensitive
        
        if 'boy' in text or 'boys' in text:
            return 'boys'
        if 'girl' in text or 'girls' in text:
            return 'girls'        
        return None

    # 1. Check primaryCategoryId with highest priority
    gender = check_string(name)
    if gender:
        return gender

    # 3. If no keywords are found in any priority field, default to 'unisex'
    return 'unisex'

def datetime_serializer(obj):
    """Custom JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def construct_url(base_url, product_name, id, color_id):
    # if product_name: PUMA x HELLO KITTY AND FRIENDS\u00ae Easy Rider Toddlers' Easy On Sneakers
    # Then convert it into lower then remove all special characters the put - in between spaces
    #product_name will be - puma-x-hello-kitty-and-friends-easy-rider-toddlers-easy-on-sneakers
    product_name = product_name.lower()
    product_name = re.sub(r'[^a-z0-9\s-]', '', product_name)
    product_name = re.sub(r'\s+', '-', product_name)
    product_name = product_name.strip('-')
         
    return f"{base_url}/pd/{product_name}/{id}?swatch={color_id}"

def remove_html_tags(text):
    """Remove HTML tags from a string"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def extract_composition_details(material_composition):
    """
    Combines a list of material strings into a single, comma-separated string.
    """
    details = {
        "composition": None
    }

    # Return early if the input is empty or None
    if not material_composition:
        return details
    
    # Use str.join() to correctly combine all items in the list
    details["composition"] = ", ".join(material_composition)
    
    return details

def extract_images(images, color_id):
    """
    Transforms image data, assigning special styles only to the first URL that
    contains the exact, continuous pattern for that style.
    """
    if not images or not color_id:
        return []

    transformed_list = []
    style_counter = 0
    
    # Flags to ensure special styles are only used once
    nffc_assigned = False
    nfsc_assigned = False

    # The exact, continuous patterns to search for
    nffc_pattern = f'/{color_id}/fnd/PNA/'
    nfsc_pattern = f'/{color_id}/sv03/fnd/'

    for image in images:
        url = image.get("href")
        if not url:
            continue
        
        image_style = ""

        # Check for the exact n_f_f_c pattern if it hasn't been used yet
        if not nffc_assigned and nffc_pattern in url:
            image_style = 'n_f_f_c'
            nffc_assigned = True
        
        # Check for the exact n_f_s_c pattern if it hasn't been used yet
        elif not nfsc_assigned and nfsc_pattern in url:
            image_style = 'n_f_s_c'
            nfsc_assigned = True
        
        # Fallback for all other images
        else:
            image_style = f's{style_counter}'
            style_counter += 1
        
        transformed_list.append({
            "url": url,
            "image_style": image_style
        })
        
    return transformed_list

def parse_age_range(range_str):
    """
    Parses an age range string (e.g., "1-2 y", "0-3 m") into a tuple of
    (min_months, max_months).
    """
    range_str = range_str.lower().replace(" ", "")
    
    numbers = [int(n) for n in re.findall(r'\d+', range_str)]
    if not numbers:
        return None, None

    min_val, max_val = (numbers[0], numbers[1]) if len(numbers) > 1 else (numbers[0], numbers[0])
    
    multiplier = 12 if 'y' in range_str else 1
    
    return min_val * multiplier, max_val * multiplier

def format_months_to_age_string(months):
    """
    Formats an age in months into a string (e.g., 24 -> "2y", 6 -> "6m").
    """
    if months is None or months == float('inf') or months == float('-inf'):
        return None
    
    if months % 12 == 0 and months > 0:
        return f"{months // 12}y"
    return f"{months}m"

def analyze_product_sizing(size_groups_data, kids_size_map, category_map):
    """
    Analyzes product sizes to determine all age categories and the overall min/max
    age range, considering the absolute minimum age from the categories.
    """
    # Pre-process the category map for efficient lookup
    processed_categories = {}
    for age_code, category_name in category_map.items():
        min_m, max_m = parse_age_range(age_code)
        if min_m is not None:
            processed_categories[category_name] = {'min_m': min_m, 'max_m': max_m}

    found_categories = set()
    product_min_months = float('inf')
    product_max_months = float('-inf')

    # First pass: determine product's actual age range and find overlapping categories
    for group in size_groups_data:
        for size in group.get("sizes", []):
            size_label = size.get("label")
            age_range_str = kids_size_map.get(size_label)
            
            if age_range_str:
                size_min_m, size_max_m = parse_age_range(age_range_str)
                if size_min_m is None:
                    continue

                # Update product's actual min and max age from its sizes
                product_min_months = min(product_min_months, size_min_m)
                product_max_months = max(product_max_months, size_max_m)

                # Check for overlap with each defined category
                for cat_name, cat_ranges in processed_categories.items():
                    if max(size_min_m, cat_ranges['min_m']) <= min(size_max_m, cat_ranges['max_m']):
                        found_categories.add(cat_name)
    
    # Second pass: determine the absolute minimum age from the found categories
    overall_min_months = product_min_months
    if found_categories:
        min_from_categories = min(processed_categories[cat]['min_m'] for cat in found_categories)
        overall_min_months = min(product_min_months, min_from_categories)

    # Format the final age range
    min_age_str = format_months_to_age_string(overall_min_months)
    max_age_str = format_months_to_age_string(product_max_months)

    # Consolidate results into a dictionary
    result = {
        #Convert the data to lower case for categories
        "categories": sorted([c.lower() for c in found_categories]),
        "age_range": [min_age_str, max_age_str] if min_age_str and max_age_str else []
    }
    
    return result
    

def process_product_data(base_url, fetch_date, json_data, gender):
    products = []
    skip_products = ['accessories']
    if json_data['data']['product']['productDivision'] is None or \
        json_data['data']['product']['productDivision'].lower() in skip_products or \
        json_data['data']['product']['productDivision'].lower() == 'footwear':
        return products
    
    primary_category_id = json_data['data']['product']['primaryCategoryId']
    size_chart_id = json_data['data']['product']['sizeChartId']
    
    gender = determine_gender(primary_category_id, size_chart_id)

    pid = 'pum' + json_data['data']['product']['id']
    variations = json_data['data']['product']['variations']

    # 2. If it's a kids' product, check for boys/girls ONCE, before the loops.
    if gender == "kids":
        final_gender = determine_kids_gender(json_data['data']['product']['name'])
    else:
        final_gender = gender
    
    # 3. Set the age group based on the final, corrected gender.
    if final_gender in ["boys", "girls", "unisex"] and gender == "kids":
        age_group = ['kids']
        age_range = ['1y', '17y']
    else:
        age_group = ['adult']
        age_range = ['18y']
    
    
    for variant in variations:
        size_groups = variant['sizeGroups']
        if gender == "kids":
            kids_group = analyze_product_sizing(variant['sizeGroups'], kids_size_to_age_map, age_code_to_category_map)
        for size_group in size_groups:
            sizes = size_group['sizes']
            for size in sizes:
                title = variant['name']
                product_id = variant['masterId']
                color_id = variant['colorValue']

                product_url = construct_url(base_url,title, product_id, color_id)

                discription = remove_html_tags(variant['description'])

                composition = extract_composition_details(variant['materialComposition'])

                images = extract_images(variant['images'], color_id)

                product = {
                    "product_id": pid,
                    "sub_brand": None,
                    "gender": final_gender,
                    "age_group": kids_group["categories"] if gender == "kids" else age_group,
                    "age_range": kids_group["age_range"] if gender == "kids" else age_range,
                    "date_of_scraping": parse_launch_date(fetch_date),
                    "url": product_url,
                    "title": title.lower(),
                    "description": discription,
                    "product_ref_code": product_id,
                    "color_id": f'{pid}%{color_id}',
                    "color_name": variant['colorName'].lower(),
                    "color_ref_code": color_id,
                    "sku":f'{pid}%{product_id}_{color_id}s{size['label']}',
                    "size_name": size['label'],
                    "size_ref_code": None,
                    "price": variant['salePrice'],
                    "launch_price": variant['price'],
                    "availability": "in_stock" if size['orderable'] else "out_of_stock",
                    "origin": None,
                    "images": images,
                    "demand": None,
                    "composition": composition["composition"]
                }
                products.append(product)
    return products

def get_folders(sub_folders, exclude_folder=None):
    """
    Lists only the subdirectories within a given folder, optionally excluding some.
    """
    try:
        # Get all item names in the directory
        all_items = os.listdir(sub_folders)
        
        # Filter the list to include only items that are actual directories
        folders = [
            item for item in all_items 
            if os.path.isdir(os.path.join(sub_folders, item))
        ]
        
        # Apply the exclusion filter if provided
        if exclude_folder:
            folders = [folder for folder in folders if folder not in exclude_folder]
            
        return folders
        
    except FileNotFoundError:
        print(f"Warning: Directory not found: {sub_folders}")
        return []

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
                    with open(f'{country}/{fetch_date}/Data/apparel_error_log.txt', 'a', encoding='utf-8') as log_file:
                        log_file.write(f"Error processing {file_path}: {str(e)}\n")
                        log_file.write(traceback.format_exc() + '\n')
    
    # Save all products to a single JSON file
    output_file = os.path.join(country, fetch_date, 'Data', f'apparel_products_data_{country}.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False,  default=datetime_serializer)
    print(f'\nAll products saved to {output_file}')
    
    # Save processing log
    log_file = os.path.join(country, fetch_date, 'Validation', f'apparel_sku_log_{fetch_date}.csv')
    pd.DataFrame(log_data).to_csv(log_file, index=False)
    print(f'SKU log saved to {log_file}')

def upload_to_json_apparel(countries, fetch_date, re_run=False):   
    for country, base_url in countries.items():
        # Ensure the directory structure exists
        # Check file existence of products_data
        data_file = os.path.join(country, fetch_date, 'Data', f'apparel_products_data_{country}.json')
        if not re_run and os.path.exists(data_file):
            print(f"Data file {data_file} already exists. Skipping processing for {country}.")
            continue
        os.makedirs(os.path.join(country, fetch_date, 'Data'), exist_ok=True)
        print(f"\nProcessing data for {country}...")
        process_and_save_to_json(base_url['base_url'], fetch_date, country)
    
    print("\nData processing completed for all countries.")