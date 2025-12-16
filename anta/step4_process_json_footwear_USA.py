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

def get_age_group(age_range):
    new_born_ages = ['0m', '1m', '2m', '3m', '4m', '5m', '6m']
    baby_ages = ['7m', '8m', '9m', '10m', '11m', '12m', '13m', '14m', '15m', '16m', '17m', '18m', '19m', '20m', '21m', '22m', '23m', '24m']
    junior_ages = ['2y', '3y', '4y', '5y', '6y', '7y']
    senior_ages = ['8y', '9y', '10y', '11y', '12y']
    teen_ages = ['13y', '14y', '15y', '16y', '17y']
    adult_ages = ['18y']

    age_goup_list = ['new_born', 'baby', 'junior', 'senior', 'teen', 'adult']
    age_group = [] 

    if not age_range:
        return ['others']

    if len(age_range) == 1:
        val = age_range[0]
        if val in new_born_ages:
            return ['new_born']
        elif val in baby_ages:
            return ['baby']
        elif val in junior_ages:
            return ['junior']
        elif val in senior_ages:
            return ['senior']
        elif val in teen_ages:
            return ['teen']
        elif val in adult_ages:
            return ['adult']
        else:
            return ['others']

    else:
        age_group = []
        start = age_range[0]
        end = age_range[-1]
        
        sindex = -1
        eindex = -1

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

        if sindex != -1 and eindex != -1:
            for i in range(sindex, eindex + 1):
                age_group.append(age_goup_list[i])

        if not age_group:
            age_group = ['others']
            
    return age_group

def remap_age_range(age_range):
    if len(age_range) > 1:
        age_range = [age_range[0], age_range[-1]]

    if age_range[0] == '1y':
        if len(age_range) == 1:
            age_range = ['12m']
        else:
            end = age_range[-1]
            age_range = ['12m', end]

    if len(age_range) > 1 and age_range[-1] == '2y':
        end = '24m'
        age_range = ['12m', end]

    if len(age_range) > 1 and age_range[0] == '24m':
        end = str(int(int(age_range[-1][:-1])/12)) + 'y'
        age_range = ['2y', end]
    

    return age_range

def get_age_range(size):
    if size and 'Y' in size:
        size_part = size.split(' ')[0]
        if '-' in size_part:
            ranges = size_part.split('-')
            start = ranges[0].strip().split('.')[0]
            end = ranges[1].replace('Y', '').strip().split('.')[0]
            age_range = [start + 'y', end + 'y']
        else:
            size_num = size_part.replace('Y', '').strip().split('.')[0]
            age_range = [size_num + 'y']
    else:
        age_range = ['18y']

    age_range = remap_age_range(age_range)
    return age_range


def remap_gender(json_data):
    title = json_data.get('title')
    handle = json_data.get('handle')

    combined = f"{title} {handle}".lower()

    # Check for women's/female keywords
    if any(k in combined for k in ["women's", 'womens', 'women', 'woman', 'girl', 'girls']):
        return 'female'

    # Check for men's/male keywords
    if any(k in combined for k in ["men's", 'mens', 'men', 'man', 'boy', 'boys']):
        return 'male'

    # Check for kids/unisex keywords
    if any(k in combined for k in ['kids', 'kid',  'youth']):
        return 'unisex'

    return 'unisex'

def create_individual_json(json_data, today_str):
    all_products = []
    try:
        base_url = 'https://anta.com/'
        name = json_data['title'].lower().strip().replace('é', 'e').replace('à', 'a').replace('è', 'e').replace('ì', 'i').replace('ò', 'o').replace('ù', 'u')
        gender = remap_gender(json_data)
        descriptions_parts = json_data.get("description")
        descriptions_regx = re.sub(r'<.*?>', '', descriptions_parts)
        if descriptions_regx:
            descriptions = descriptions_regx.strip().replace("“", "").replace("”", "").replace("\n", "").replace("—", "").replace("’", "'")
        else:
            descriptions = None 
        
        occasion = json_data.get("type", "").split(" ")[0].lower() if json_data.get("type") else ""
        if any (occ in occasion for occ in ['slides','trail']):
            occasion = None
        
        # Extract materials
        composition_text = json_data.get("composition", "")
        match = re.search(r'Upper:\s*([^,]+)', composition_text)
        upper = match.group(1).strip() if match else ""
        
        match = re.search(r'Outsole:\s*([^,]+)', composition_text)
        sole = match.group(1).strip() if match else ""
        
        # Get price (convert from pence to pounds)
        price = json_data.get('price', 0) / 100 if json_data.get('price') else 0
        launch_price = json_data.get('compare_at_price', 0) / 100 if json_data.get('compare_at_price') else None
        if launch_price is None or launch_price == 0:
            launch_price = price
        
        # Get all color images once
        all_color_images = get_color_images(json_data)
        category = json_data.get("type", "").split(" ")[0].lower() if json_data.get("type") else ""
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
                    "age_group": get_age_group(get_age_range(size)),
                    "age_range": get_age_range(size),
                    "date_of_scraping": parse_launch_date(today_str),
                    "url": url,
                    "title": name.lower(),
                    "description": descriptions,
                    "product_ref_code": None,
                    "color_id": f'{product_id}%{color_id}',
                    "color_name": cname.lower() if cname else "",  
                    "color_ref_code": None,
                    "sku": f'{product_id}%{sku}',
                    "size_name": size,
                    "size_ref_code": None,
                    "price": price,
                    "launch_price": launch_price,
                    "availability": availability,
                    "sole_material": sole,
                    "upper_material": upper,
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
    except Exception as e:
        import traceback
        print(f"Error in create_individual_json: {e}")
        print(f"Product: {json_data.get('title', 'Unknown')}")
        traceback.print_exc()
        raise
    return all_products
    
key = ['Shoes','Slides','Sneakers','Sandals','Boots']

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
                
                product_type = data.get("type", "")
                
                # Skip if product type does NOT contain footwear keywords
                if not any(k.lower() in product_type.lower() for k in key):
                    continue
                products = create_individual_json(data, today_str)
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
        'USA': 'https://anta.com'
    }

    save_country_data_to_json(countries, today_str, re_run=False)