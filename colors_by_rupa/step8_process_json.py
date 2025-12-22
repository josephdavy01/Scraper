import logging
import os
import json
import re
import html
from datetime import date
import traceback
from datetime import datetime
import math



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
    if not age_range:
        return []

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
    age_range = []
    if not size:
        return ['18y']
    size = size.strip().lower().replace(" ", "")
    if size == 'm':
        return ['18y']

    # -------- Months --------
    if 'm' in size:
        size = size.replace('m', '')
        if '-' in size:
            start, end = size.split('-')
            age_range = [start + 'm', end + 'm']
        else:
            age_range = [size + 'm']

    # -------- Years --------
    elif 'year' in size or 'y' in size:
        size = size.replace('years', '').replace('year', '').replace('y', '')
        if '-' in size:
            start, end = size.split('-')
            age_range = [start + 'y', end + 'y']
        else:
            age_range = [size + 'y']

    else:
        age_range = ['18y']

    return age_range


def remap_gender(json_data):
    name = json_data.get("name").lower()    
    if any(k in name for k in ["women", "womens", "woman", "girl", "girls"]):
        return "female"

    if any(k in name for k in ["men", "mens", "man", "boy", "boys","kids","kid"]):
        return "male"
        
    return "unisex"
    
def get_images(json_data, color_name):
    color_images = []
    variants = json_data.get("variants", [])
    for variant in variants:
        color = variant.get("color")
        images = variant.get("images", [])
        if color_name and color and color_name.lower() == color.lower():
            for index, img in enumerate(images):
                color_images.append({
                    "url": img,
                    "image_style": f"s{index}"
                })
            break
    return color_images

def create_individual_json(base_url, today_str, json_data, gender,cdict):
    all_products = []
    errors = []
    base_url = "https://livecolors.in/"
    try:
        variants = json_data.get("variants") or []
        url = json_data.get("url")
        name = json_data.get("name").lower() 
        gender = remap_gender(json_data)
        country = "india"
        price = json_data.get('price')
        if price:
            price = float(price.replace("Rs.", "").replace(",", "").strip())
        pid = 'clr' + str(json_data.get("sku", "")).replace("None", "")
        description_parts = json_data.get("description") or []
        if isinstance(description_parts, list):
             description_parts = "".join(description_parts)
        elif not description_parts:
             description_parts = ""
        description_part = json_data.get("detailed_description") or ""
        description = str(description_parts) + " " + str(description_part)
        clean_description = re.sub(r"<.*?>", "", description).strip().replace("\n", "|")
        composition = None
        composition_list = json_data.get("composition")
        if composition_list:
            for comp in composition_list:
                if "%" in comp:
                    composition = comp
                    break
        else:
            if description:
                match = re.search(r"\b\d+%\s*[A-Za-z ]+", description)
                if match:
                    composition = match.group().strip()
                        
        for variant in variants:
            color_name = variant.get("color").strip().lower()
            color_clean = color_name.replace("\n", "").lower()
            
            cid = cdict.get(color_clean) 
            
            sizes = variant.get("sizes", {})
            for size, stock in sizes.items():
                size = size.replace(" ", "")
                sku = f"{cid}-{size}"
                availability = "in_stock" if stock == "in_stock" else "out_of_stock"
                age_range = get_age_range(size)
                age_group = get_age_group(age_range)
                images = get_images(json_data, color_name)

                entry = {
                        "product_id": pid,
                        "gender": gender,
                        "age_group": age_group,
                        "age_range": age_range,
                        "date_of_scraping": parse_launch_date(today_str),
                        "url": url,
                        "title": name,
                        "description": clean_description,
                        "product_ref_code": None,
                        "color_id":f"{pid}%{cid}",
                        "color_name": color_name,
                        "color_ref_code": None,
                        "sku": f"{pid}%{sku}",
                        "size_name": size,
                        "size_ref_code": None,
                        "price": price,
                        "launch_price": price,
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

    json_data_folder = os.path.abspath(os.path.join(country, today_str, 'Json_data'))
    cid_path = 'colors_cid_remapping.json' # Define cid_path
    cdict = {}
    if os.path.exists(cid_path):
        try:
            with open(cid_path, 'r') as f:
                cdict = json.load(f)
        except json.JSONDecodeError:
            cdict = {}

    if not os.path.exists(json_data_folder):
        logging.info(f"Warning: Json_data folder not found: {json_data_folder}")
        return [], [{"error": f"Folder not found: {json_data_folder}"}]

    for root, _, files in os.walk(json_data_folder):
        relative_path = os.path.relpath(root, json_data_folder)
        if relative_path == '.':
            gender_hint = "N/A"
        else:
            gender_hint = relative_path.split(os.sep)[0]
            
        for file in files:
            if not file.endswith('.json'):
                continue

            file_path = os.path.join(root, file)

            try:
                with open(file_path, 'r', encoding='utf-8') as json_file:
                    data = json.load(json_file)

                products, errors = create_individual_json(base_url, today_str, data, gender_hint, cdict)
                if products:
                    all_country_products.extend(products)
                    logging.info(f"Processed {file}: {len(products)} products")
                else:
                    logging.warning(f"Skipping {file} - {errors}")
                    error_logs.append({
                        "file": file,
                        "path": file_path,
                        "gender": gender_hint,  
                        "reasons": errors
                    })

            except Exception as e:
                logging.error(f"Error processing {file_path}: {e}")
                traceback.print_exc()
                error_logs.append({ 
                    "file": file,
                    "path": file_path,
                    "gender": gender_hint,
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
            base_url = 'https://www.jockey.in/products/'

        output_dir = os.path.join(country, today_str, 'Final_json')
        output_file = os.path.join(output_dir, f'{country}_apparel_data.json')


        if not re_run and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            logging.info(f"Data file {output_file} already exists and is not empty. Skipping processing for {country}.")
            continue

        logging.info(f"Processing {country} apparel...")
        all_products, error_logs = process_jsons(base_url, today_str, country, execution_config)

        os.makedirs(output_dir, exist_ok=True)

        if all_products:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_products, f, indent=4, default=datetime_serializer)
                logging.info(f"Saved {len(all_products)} products to {output_file}")
            except Exception as e:
                logging.error(f"Error saving data for {country}: {e}")
        else:
            logging.warning(f"No products found for {country}")

        if error_logs:
            error_file = os.path.join(output_dir, f'{country}_error_processing_data.json')
            try:
                with open(error_file, 'w', encoding='utf-8') as f:
                    json.dump(error_logs, f, indent=4, ensure_ascii=False)
                logging.info(f"Saved {len(error_logs)} error logs to {error_file}")
            except Exception as e:
                logging.error(f"Error saving error logs for {country}: {e}")


        logging.info(f"Apparel data processing for {country} completed!")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = "2025-12-11"
  

    countries = {
        'India': 'https://www.jockey.in/products/'
    }

    save_country_data_to_json(countries, today_str,re_run=False)
