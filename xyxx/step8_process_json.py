import os
import json
import re
import html
from datetime import date
import traceback
from datetime import datetime
import math
from alert import raise_ticket


def get_folders(sub_folders, exclude_folder=None):
    """Get list of folders excluding specified ones."""
    if exclude_folder is None:
        exclude_folder = []
    if not os.path.exists(sub_folders):
        return []

    folders = []
    for item in os.listdir(sub_folders):
        item_path = os.path.join(sub_folders, item)
        if os.path.isdir(item_path) and item not in exclude_folder:
            folders.append(item)
    return folders


def parse_launch_date(date_string):
    """Parse date string in multiple formats."""
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


def datetime_serializer(obj):
    """Serialize datetime objects to ISO format."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


# Global dictionaries for PID and CID mappings
pdict = {}
cdict = {}

def get_pid(handle):
    """Get PID for a product handle from pdict"""
    for pid, handles in pdict.items():
        if handle in handles:
            return pid
    return '0000000'

def get_cid(color_name):
    """Get CID for a color name from cdict"""
    return cdict.get(color_name, None)

def get_images(images_data):
    result = []
    # images_data is already a list, not a dict
    images = images_data if isinstance(images_data, list) else []
    for img in images:
        result.append({
            "url": img,
            "image_style": "s0"
        })
    return result


def create_individual_json(base_url, today_str, json_data, gender):
    all_products = []
    errors = []
    try:
        variants = json_data.get('variants', [])
        if not variants:
            errors.append("No variants found")
            return all_products, errors
            
        name = variants[0].get('name', '').split("-")[0].strip().lower()  
        cname = json_data.get("color").lower()  
        if name and cname.lower() in name.lower():
            name = name.replace(cname,"").strip()
        url = json_data.get('product_url')
        
        # Get description
        description_list = json_data.get('description')
        if isinstance(description_list, list):
            description = ' '.join(description_list).replace("\n", "").replace("\\", "").replace(" ", "")
        else:
            description = str(description_list).replace("\n", "").replace("\\", "")
        
        product_url = json_data.get("product_url", "")
        handle = product_url.rstrip("/").split("/")[-1]
        
        pid = 'xyx' + get_pid(handle)
             
        # Get CID
        cid = get_cid(cname)

        composition_lines = None

        for feature in json_data.get("description", []):
            feature = feature.split("\n")

            for line in feature:
                if "intellifresh" in line.lower():
                    continue
                if "%" in line:
                    composition_lines = line.strip()
                    break

            if composition_lines:
                break
            
        composition = composition_lines if composition_lines else None


        price = math.ceil(variants[0].get('price', 0) / 100)

        compare_price = variants[0].get('compare_at_price')
        oldprice = math.ceil(compare_price / 100) if compare_price else price
     
        images = get_images(json_data.get("images", []))
        
        # Create one product entry per variant
        for variant in variants:
            if variant.get('option1'):
                size = variant.get('option1')
                sku = variant.get('sku')
                
                # Skip variants without SKU
                if not sku:
                    errors.append(f"Variant {variant.get('id')} has no SKU, skipping")
                    continue
                    
                if variant.get('available') == True:
                    availability = "in_stock"
                else:
                    availability = "out_of_stock"

                entry = {
                    "product_id": pid,
                    "gender": "male",
                    "age_group": ['adult'],
                    "age_range": ['18y'],
                    "date_of_scraping": parse_launch_date(today_str),
                    "url": url,
                    "title": name,
                    "description": description,
                    "product_ref_code": None,
                    "color_id":f"{pid}%{cid}",
                    "color_name": cname,
                    "color_ref_code": None,
                    "sku": f"{pid}%{sku}",
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

                all_products.append(entry)

    except Exception as e:
        errors.append(f"Error processing product: {str(e)}")

    return all_products, errors


def process_jsons(base_url, today_str, country, execution_config=None):
    all_country_products = []
    error_logs = []

    gender_folder = os.path.join(country, today_str, 'Json_data')

    if not os.path.exists(gender_folder):
        print(f"Warning: Gender folder not found: {gender_folder}")
        return [], [{"error": f"Folder not found: {gender_folder}"}]

    genders = get_folders(gender_folder, [])

    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, [])

        for category in categories:
            file_folder = os.path.join(category_folder, category)

            if not os.path.exists(file_folder):
                continue

            files = os.listdir(file_folder)

            for file in files:
                if not file.endswith('.json'):
                    continue

                file_path = os.path.join(file_folder, file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)

                    products, errors = create_individual_json(base_url, today_str, data, gender)

                    if products:
                        all_country_products.extend(products)
                        print(f"Processed {file}: {len(products)} products")
                    else:
                        print(f"Skipping {file} - {errors}")
                        error_logs.append({
                            "file": file,
                            "path": file_path,
                            "gender": gender,
                            "category": category,
                            "reasons": errors
                        })

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()
                    error_logs.append({
                        "file": file,
                        "path": file_path,
                        "gender": gender,
                        "category": category,
                        "reasons": [str(e)]
                    })

    return all_country_products, error_logs


def save_country_data_to_json(countries, today_str, re_run=False, execution_config=None):
    """Save processed data to JSON files for each country."""
    country_list = countries.keys() if isinstance(countries, dict) else countries
    # today_str = "2025-12-09"

    for country in country_list:
        if isinstance(countries, dict):
            base_url = countries[country]
        else:
            base_url = 'https://xyxxcrew.com/products/'

        output_dir = os.path.join(country, today_str, 'Final_json')
        output_file = os.path.join(output_dir, f'{country}_apparel_data.json')

        if not re_run and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print(f"Data file {output_file} already exists and is not empty. Skipping processing for {country}.")
            continue

        print(f"Processing {country} apparel...")
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

        print(f"Apparel data processing for {country} completed!")


if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    pid_path = 'xyxx_pid_remapping.json'
    cid_path = 'xyxx_cid_remapping.json'

    if os.path.exists(pid_path):
        try:
            with open(pid_path, 'r') as json_file:
                content = json_file.read().strip()
                if content:
                    pdict = json.loads(content)
                else:
                    pdict = {}
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in {pid_path}, using empty dictionary")
            pdict = {}
    else:
        pdict = {}

    if os.path.exists(cid_path):
        try:
            with open(cid_path, 'r') as json_file:
                content = json_file.read().strip()
                if content:
                    cdict = json.loads(content)
                else:
                    cdict = {}
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in {cid_path}, using empty dictionary")
            cdict = {}
    else:
        cdict = {}

    countries = {
        'India': 'https://xyxxcrew.com/products/'
    }

    save_country_data_to_json(countries, today_str, re_run=False)
