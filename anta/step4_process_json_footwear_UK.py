import os
import json
import re
from collections import OrderedDict
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

def get_color_images(json_data):
    color_images = OrderedDict()

    variants = json_data.get('variants', [])
    media = json_data.get('media', [])

    # Get featured image position for each color
    color_positions = OrderedDict()

    for variant in variants:
        color_name = variant.get('option1')
        if color_name in color_positions:
            continue

        featured_image = variant.get('featured_image', {})
        if featured_image and 'position' in featured_image:
            color_positions[color_name] = featured_image['position']

    # Sort colors by position
    sorted_colors = sorted(color_positions.items(), key=lambda x: x[1])

    # Determine position ranges
    color_ranges = OrderedDict()
    for i, (color_name, start_pos) in enumerate(sorted_colors):
        if i < len(sorted_colors) - 1:
            end_pos = sorted_colors[i + 1][1] - 1
        else:
            end_pos = len(media)

        color_ranges[color_name] = (start_pos, end_pos)
        color_images[color_name] = []

    # Assign images to colors (NO image_style yet)
    for media_item in media:
        if media_item.get('media_type') != 'image':
            continue

        position = media_item.get('position')
        src = media_item.get('src') or media_item.get('preview_image', {}).get('src')

        if not src:
            continue

        if src.startswith('//'):
            src = f"https:{src}"
        elif not src.startswith('http'):
            src = f"https://{src}"

        for color_name, (start_pos, end_pos) in color_ranges.items():
            if start_pos <= position <= end_pos:
                color_images[color_name].append({
                    'url': src
                })
                break

    # 🔹 RESET image_style PER COLOR
    for color_name, images in color_images.items():
        for idx, img in enumerate(images):
            img['image_style'] = f"s{idx}"

    return color_images



def get_folders(path, exclude_list):
    """Get list of subdirectories in a path, excluding those in exclude_list"""
    if not os.path.exists(path):
        return []
    
    folders = []
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path) and item not in exclude_list:
            folders.append(item)
    return folders

def datetime_serializer(obj):
    """JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def remap_gender(json_data):
    title = json_data.get('title', '')
    handle = json_data.get('handle', '')

    combined = f"{title}{handle}".lower()

    if any(k in combined for k in [' women ', ' womens', '-women', '/women']):
        return 'female'

    if any(k in combined for k in [' men ', ' mens', '-men', '/men']):
        return 'male'

    return 'unisex'

key = ["Shoes"]

def create_individual_json(today_str, json_data):
    all_products = []
    base_url = 'https://uk.anta.com'
    name = json_data['title'].lower().strip().replace('é', 'e').replace('à ', 'a').replace('è', 'e').replace('ì', 'i').replace('ò', 'o').replace('ù', 'u')
    gender = remap_gender(json_data)
    descriptions_parts = json_data.get("body_html", "")
    descriptions_regx = re.sub(r'<.*?>', '', descriptions_parts)
    if "Description" in descriptions_regx:
        descriptions = descriptions_regx.split("Description")[-1].strip().replace("“", "").replace("”", "").replace("\n", "").replace("—", "").replace("’", "'")
    else:
        descriptions = None 
    
    occasion = json_data.get("type").split(" ")[0].lower()
 
    # Extract materials
    upper_material = ""
    match = re.search(r'Upper:\s*([^<\n]+)', descriptions_regx)
    if match:
        upper_material = match.group(1).strip().lower()
    
    sole_material = ""
    match = re.search(r'Outsole:\s*([^<\n]+)', descriptions_regx)
    if match:
        sole_material = match.group(1).strip().lower()
    
    # Get price (convert from pence to pounds)
    price = json_data.get('price', 0) / 100 if json_data.get('price') else 0
    launch_price = json_data.get('compare_at_price', 0) / 100 if json_data.get('compare_at_price') else None
    if launch_price is None or launch_price == 0:
        launch_price = price
    
    # Get all color images once
    all_color_images = get_color_images(json_data)
    category = json_data.get("type").split(" ")[0].lower()
    color_id = None

    variants = json_data.get('variants', [])
    for variant in variants:
        sku = variant.get('sku')
        featured_image = variant.get("featured_image", {})
        product_id = "ant" + str(featured_image.get("product_id"))  
        color_id = featured_image.get("id")
        cname = variant.get('option1')
        size = variant.get('option2')   # Size name
        variant_url = "variant=" + str(variant.get('id'))
        url = base_url + '/products/' + json_data['handle']+"?" +variant_url
        
        # Get images for this specific color using ORIGINAL color name
        images = all_color_images.get(cname, [])
        
        # Availability
        if variant.get('available') == True:
            availability = 'in_stock'
        else:
            availability = 'out_of_stock'
          
        entry = {
                "product_id": product_id,
                "gender": gender,
                "age_group": ['adult'],
                "age_range": ['18y'],
                "date_of_scraping": parse_launch_date(today_str),
                "url": url,
                "title": name.lower(),
                "description": descriptions,
                "product_ref_code": None,
                "color_id": f'{product_id}%{color_id}',
                "color_name": cname.lower(),  
                "color_ref_code": None,
                "sku": f'{product_id}%{sku}',
                "size_name": size,
                "size_ref_code": None,
                "price": price,
                "launch_price": launch_price,
                "availability": availability,
                "sole_material": sole_material,
                "upper_material": upper_material,
                "occasion": occasion,
                "shoe_type": None, 
                "closure_type": None,
                "toe_shape": None,
                "heel_type": None,
                "weight": None,
                "heel_to_toe_drop": None,
                "origin": None,
                "images": images
                }
        all_products.append(entry)
    return all_products


def process_jsons(base_url, today_str, country, execution_config=None):
    all_country_products = []
    error_logs = []

    json_data_folder = os.path.join(country, today_str, 'Json_data')

    if not os.path.exists(json_data_folder):
        print(f"Warning: Json_data folder not found: {json_data_folder}")
        return [], [{"error": f"Folder not found: {json_data_folder}"}]

    # Get all category folders (basketball, lifestyle, running, etc.)
    categories = get_folders(json_data_folder, [])

    for category in categories:
        category_folder = os.path.join(json_data_folder, category)

        if not os.path.exists(category_folder):
            continue

        files = os.listdir(category_folder)

        for file in files:
            if not file.endswith('.json'):
                continue

            file_path = os.path.join(category_folder, file)

            try:
                with open(file_path, 'r', encoding='utf-8') as json_file:
                    data = json.load(json_file)
                
                # Extract product type
                product_type = data.get("type", "")
                
                # ONLY process if "Shoes" is in the product type (skip apparel, etc.)
                if not any(k.lower() in product_type.lower() for k in key):
                    print(f"Skipping {category}/{file}: Type '{product_type}' does not contain footwear keyword")
                    continue
                  
                products = create_individual_json(today_str, data)

                if products:
                    all_country_products.extend(products)
                    print(f"Processed {product_type} {category}/{file}: {len(products)} products")
                else:
                    print(f"Skipping {file} - no products generated")

            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                error_logs.append({
                    "file": file,
                    "path": file_path,
                    "category": category,
                    "reasons": [str(e)]
                })

    return all_country_products, error_logs



def save_country_data_to_json(countries, today_str, re_run=False, execution_config=None):
    """Save processed data to JSON files for each country."""
    country_list = countries.keys() if isinstance(countries, dict) else countries

    for country in country_list:
        if isinstance(countries, dict):
            base_url = countries[country]
        else:
            base_url = 'https://uk.anta.com'

        output_dir = os.path.join(country, today_str, 'Final_json')
        output_file = os.path.join(output_dir, f'{country}_footwear_data.json')

        if not re_run and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print(f"Data file {output_file} already exists and is not empty. Skipping processing for {country}.")
            continue

        print(f"Processing {country} footwear...")
        all_products, error_logs = process_jsons(base_url, today_str, country, execution_config)

        os.makedirs(output_dir, exist_ok=True)

        if all_products:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_products, f, indent=4, default=datetime_serializer)
                print(f"Saved {len(all_products)} products to {output_file}")
            except Exception as e:
                print(f"Error saving data for {country}: {e}")
        else:
            print(f"No products found for {country}")

        if error_logs:
            error_file = os.path.join(output_dir, f'{country}_error_processing_data.json')
            try:
                with open(error_file, 'w', encoding='utf-8') as f:
                    json.dump(error_logs, f, indent=4, ensure_ascii=False)
                print(f"Saved {len(error_logs)} error logs to {error_file}")
            except Exception as e:
                print(f"Error saving error logs for {country}: {e}")

        print(f"footwear data processing for {country} completed!")


if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')

    countries = {
        'UK': 'https://uk.anta.com'
    }

    save_country_data_to_json(countries, today_str, re_run=False)