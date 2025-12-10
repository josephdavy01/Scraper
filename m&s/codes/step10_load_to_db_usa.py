import os
import json
import re
import pymongo
from datetime import datetime, date

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

def process_data(json_data, today_date, gender):
    temp = []
    data = json_data.get('product_details', {})
    brand_name = data.get("Brand_name", "").strip().lower()
    sizes = data.get('product_size', {})
    valid_sizes = {
        k: v for k, v in sizes.items()
        if not (k == 'Select Size' or k.startswith('QTY'))
    }
    if not valid_sizes:
        print(f"No valid sizes found for product: {data.get('pid', 'unknown')}")
        return []
    product_description_details = data.get('product_description', {'product_description': '', 'product_id': ''})
    reference_code = product_description_details.get('product_id', '')
    product_id = reference_code.replace('/', '') if reference_code else data.get('pid', 'unknown')
    product =  product_id
    age_group = ['adult']
    age_range = ['18y']
    product_url = data.get('url', '')
    product_color_id = data.get('product_color_id', {})
    if product_color_id:
        color_id = product_color_id.get('color_id', 'unknown')
        color_name = product_color_id.get('color_name', 'unknown')
    else:
        match = re.search(r'color=([A-Za-z0-9]+)', product_url)
        color_id = match.group(1) if match else 'unknown'
        color_name = 'unknown'
    prizes = data.get('details_and_cares', {}).get('prize', {'current_prize': 0, 'old_prize': 0})
    current_prize = prizes.get('current_prize', 0)
    old_prize = prizes.get('old_prize', 0)
    json_data_field = data.get('json_data', {})
    page_data = json_data_field.get('product_details', {})
    product_title = page_data.get('Product_title') or data.get('Product_title', '')
    page_title = product_title
    description = product_description_details.get('product_description', '')
    reference_code = product_description_details.get('product_id', '')
    skip_base = [
        "boot", "bag", "belt", "scarf", "neckerchief", "hat", "beanie",
        "glove", "mitten", "loafer", "sunglass", "flat", "sandle",
        "slipper", "slider", "shoe", "heal", "pump", "sock", "handkerchief", "tie", "hat", "brim",
        "trainer", "trilby", "cap", "stormwear", "backpack", "washbag", "mule", "liner"
    ]
    skip_keywords = [w for word in skip_base for w in (word, word + "s")]
    pattern = re.compile(r"\b(" + "|".join(skip_keywords) + r")\b", re.IGNORECASE)
    if pattern.search(page_title.lower()):
        print(f"Skipping product due to keyword match in title: {product_id}")
        return []

    details_and_cares = data.get("details_and_cares", {})
    images = details_and_cares.get("image", [])
    processed_images = []
    for img_url in images:
        if "_EC_90" in img_url:
            processed_images.append({"url": img_url, "image_style": "s0"})
        else:
            processed_images.append({"url": img_url, "image_style": "s0"})
    product_composition = details_and_cares.get('Composition', '')
    date_of_scraping = parse_launch_date(today_date)
    for size_key, size_val in valid_sizes.items():
        if 'Out of Stock' in size_key:
            availability = 'out_of_stock'
            size_key_clean = re.sub(r'\s*Out of Stock\s*', '', size_key).strip()
        elif 'Low in Stock' in size_key:
            availability = 'low_in_stock'
            size_key_clean = re.sub(r'\s*Low in Stock\s*', '', size_key).strip()
        else:
            availability = 'in_stock'
            size_key_clean = size_key.strip()
        us_match = re.search(r'US\s*([0-9X]+[A-Z]?\s*[A-Z]*)', size_key_clean, flags=re.IGNORECASE)
        if us_match:
            size_core = us_match.group(1).replace(' ', '')
            size_name = re.sub(r'[-].*', '', size_core)
            size_name = f"US{size_name}"  
        else:
            size_name = size_key_clean

        entry = {
            "product_id": product,
            "sub_brand": brand_name,
            "gender": gender.lower(),
            "age_group": age_group,
            "age_range": age_range,
            "date_of_scraping": date_of_scraping,
            "url": product_url,
            "title": page_title,
            "description": description,
            "product_ref_code": reference_code,
            "color_id": f'{product}%{color_id}',
            "color_name": color_name.lower(),
            "color_ref_code": f'{product_id}%{color_id}',
            "sku": f'{product}%{product_id}c{color_id}s{size_name}',
            "size_name": size_name,
            "size_ref_code": None,
            "price": current_prize,
            "launch_price": old_prize,
            "availability": availability,
            "demand": None,
            "composition": product_composition,
            "origin": None,
            "images": processed_images
        }
        temp.append(entry)
    return temp

def process_jsons(base_dir, scraping_date, collection):
    scraping_dates = set()
    file_dates = []
    if not os.path.isdir(base_dir):
        print(f"Base directory does not exist: {base_dir}")
        return {"scraping_dates": scraping_dates, "file_dates": file_dates}

    genders = os.listdir(base_dir)
    for gender in genders:
        converted_gender = 'female' if gender.lower() == 'women' else 'male' if gender.lower() == 'men' else gender
        gender_folder = os.path.join(base_dir, gender)
        if not os.path.isdir(gender_folder):
            continue
        categories = os.listdir(gender_folder)
        for category in categories:
            category_folder = os.path.join(gender_folder, category)
            if not os.path.isdir(category_folder):
                continue
            files = [f for f in os.listdir(category_folder) if f.endswith('.json')]
            for file in files:
                file_path = os.path.join(category_folder, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    temp = process_data(json_data, scraping_date, converted_gender)
                    if temp:
                        collection.insert_many(temp)
                        for entry in temp:
                            scraping_dates.add(entry['date_of_scraping'].strftime('%Y-%m-%d'))
                        stat = os.stat(file_path)
                        file_dates.append({
                            "file_path": file_path,
                            "created": datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
    return {"scraping_dates": scraping_dates, "file_dates": file_dates}

def main(single_day=None):
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    countries = ['USA']
    today_date = datetime.now().date()
    all_dates = {'scraping_dates': set(), 'file_dates': []}

    for country in countries:
        data_dir = f'{country}/Data'
        if not os.path.isdir(data_dir):
            print(f"Skipping {data_dir}: Directory does not exist")
            continue

        # Determine folders to process
        if single_day:
            folders_to_process = [single_day]  # Only process this specific date
        else:
            folders_to_process = [f for f in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, f))]

        for date_folder in folders_to_process:
            try:
                folder_date = datetime.strptime(date_folder, '%Y-%m-%d').date()
                if not single_day and folder_date >= today_date:
                    continue  # Skip future folders for bulk
            except ValueError:
                print(f"Skipping {date_folder}: Invalid date format")
                continue

            base_dir = os.path.join(data_dir, date_folder, 'Json_data')
            if not os.path.isdir(base_dir):
                print(f"Skipping {base_dir}: Directory does not exist")
                continue

            db = client['tg_analytics']
            collection = db[f'crawler_sink_marknspencer_group_{country.lower()}']
            print(f"Processing {base_dir} for {country}")
            country_dates = process_jsons(base_dir, date_folder, collection)
            all_dates['scraping_dates'].update(country_dates['scraping_dates'])
            all_dates['file_dates'].extend(country_dates['file_dates'])

        print(f"Finished processing for {country}")

    print("\nScraping Dates (date_of_scraping):")
    for date_str in sorted(all_dates['scraping_dates']):
        print(date_str)
    print("\nFile Creation and Modification Dates:")
    for file_date in all_dates['file_dates']:
        print(f"File: {file_date['file_path']} | Created: {file_date['created']} | Modified: {file_date['modified']}")

    client.close()
    print("Done!")


if __name__ == '__main__':
    # To process a single day, pass 'YYYY-MM-DD', e.g., main('2025-09-20')
    # To process all available folders (bulk), call main() without argument
    main()