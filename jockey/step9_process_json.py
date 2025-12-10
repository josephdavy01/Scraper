import logging
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
    if size and 'yrs' in size.lower():
        if '-' in size:
            ranges = size.split(' ')[0].split('-')
            start = ranges[0].strip()
            end = ranges[1].strip()
            age_range = [start + 'y', end + 'y']
        else:
            ranges = size.split(' ')[0].strip()
            age_range = [ranges + 'y']
    else:
        age_range = ['18y']  

    age_range = remap_age_range(age_range)
    return age_range


def get_pid(name, pdict):
    name = name.strip()
    for pid, pname in pdict.items():
        if pname.strip().lower() == name.lower():
            return pid
    return '0000000'

def remap_gender(json_data):
    tags = json_data.get('tags', [])

    if isinstance(tags, list):
        tags_str = ' '.join(tags).lower()

        if any(k in tags_str for k in ['men', 'mens']):
            return 'male'
        if any(k in tags_str for k in ['women', 'womens']):
            return 'female'
        if any(k in tags_str for k in ['boy', 'boys']):
            return 'male'
        if any(k in tags_str for k in ['girl', 'girls']):
            return 'female'
        if any(k in tags_str for k in ['kids', 'kid', 'unisex']):
            return 'unisex'

    return 'unisex'

def get_cid(color_name, cdict):
    return cdict.get(color_name)


def get_images(product):
    result = []
    images = product.get("images") or []

    for img in images:
        if isinstance(img, dict):
            url = img.get("src") or img.get("url")
        else:
            url = img

        if not url:
            continue

        if isinstance(url, str) and url.startswith("//"):
            url = "https:" + url

        result.append({
            "url": url,
            "image_style": "s0"
        })
    
    return result

def create_individual_json(base_url, today_str, json_data, gender,pdict,cdict):
    all_products = []
    errors = []
    base_url = "https://www.jockey.in/products/"
    try:
        variants = json_data.get("variants") or []
        url = base_url + (json_data.get('handle') or '')
        title = json_data.get("title") or ''
        name = title.rsplit(' - ', 1)[0]
        pid = 'jky' + get_pid(name, pdict)
        gender = remap_gender(json_data)
        country = "india"
        cname_parts = title.rsplit(' - ', 1)[-1] if ' - ' in title else ''
        cname = re.sub(r"\s*\(.*?\)", "", cname_parts).strip().lower()
        cid = get_cid(cname, cdict)
        raw_price = json_data.get('price')
        price = math.ceil(raw_price / 100) if raw_price is not None else None
        compare_price_raw = json_data.get('compare_at_price')
        oldprice = math.ceil(compare_price_raw / 100) if compare_price_raw is not None else price
        description = (json_data.get("description") or '').replace(" ", " ")
        clean_description = re.sub(r"<.*?>", "", description).strip().replace("\n", "|")
        if '%' in clean_description:
            comp_match = re.search(r"\b\d+%\s*[^|]+", clean_description)
            composition = comp_match.group(0).strip() if comp_match else None
        else:
            comp_match = re.search(r"Fabric Composition\s*:\s*([^\n<|]+)", clean_description, re.IGNORECASE)
            composition = comp_match.group(1).strip() if comp_match else None
        images = get_images(json_data)
        for variant in variants:
            sku = variant.get('sku')
            size = variant.get('option1')
            age_range = get_age_range(size)
            age_group = get_age_group(age_range)
            available = variant.get('available')
            if available:
                availability = "in_stock"
            else:
                availability = "out_of_stock"
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
                    "origin": f"{country}",
                    "images": images
                }
            all_products.append(entry)

    except Exception as e:
        errors.append(f"Error processing product: {str(e)}")

    return all_products, errors


def process_jsons(base_url, today_str, country, pdict, cdict, execution_config=None):
    all_country_products = []   
    error_logs = []

    json_data_folder = os.path.abspath(os.path.join(country, today_str, 'Json_data'))

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

                products, errors = create_individual_json(base_url, today_str, data, gender_hint, pdict, cdict)

                if products:
                    all_country_products.extend(products)
                    logging.info(f"Processed {file}: {len(products)} products")
                else:
                    logging.warning(f"Skipping {file} - {errors}")
                    error_logs.append({
                        "file": file,
                        "path": file_path,
                        "gender": gender_hint,
                        "category": "N/A", 
                        "reasons": errors
                    })

            except Exception as e:
                logging.error(f"Error processing {file_path}: {e}")
                traceback.print_exc()
                error_logs.append({
                    "file": file,
                    "path": file_path,
                    "gender": gender_hint,
                    "category": "N/A",
                    "reasons": [str(e)]
                })

    return all_country_products, error_logs


def save_country_data_to_json(countries, today_str, pdict, cdict, re_run=False, execution_config=None):
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
        all_products, error_logs = process_jsons(base_url, today_str, country, pdict, cdict, execution_config)

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
    # today_str = "2025-12-09"
    pid_path = 'jockey_pid_remapping.json'
    cid_path = 'jockey_cid_remapping.json'

    if os.path.exists(pid_path):
        try:
            with open(pid_path, 'r') as json_file:
                content = json_file.read().strip()
                if content:
                    pdict = json.loads(content)
                else:
                    pdict = {}
        except json.JSONDecodeError:
            logging.info(f"Warning: Invalid JSON in {pid_path}, using empty dictionary")
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
            logging.info(f"Warning: Invalid JSON in {cid_path}, using empty dictionary")
            cdict = {}
    else:
        cdict = {}

    countries = {
        'India': 'https://www.jockey.in/products/'
    }

    save_country_data_to_json(countries, today_str, pdict, cdict, re_run=False)
