import json
from datetime import datetime
import os
import pymongo
import re
from urllib.parse import quote

def parse_launch_date(date_string):
    for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d']:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    return None

def process_data(json_data, scraping_date, gender):
    data = json_data
    product_id = data['attributes']['strokeId']
    product = product_id
    age_group = ['adult']
    age_range = ['18y']
    brand_name = data['attributes'].get("brand","").strip().lower()
    reference_code = data['attributes']['strokeId']
    product_composition = data['attributes'].get('compositionList', '')
    product_name = data['attributes']['masterProductDescription']
    description = data['attributes']['masterAspirationalText']
    skip_base = [
        "boot", "bag", "belt", "scarf", "neckerchief", "hat", "beanie",
        "glove", "mitten", "loafer", "sunglass", "flat", "sandle",
        "slipper", "slider", "shoe", "heal", "pump", "sock", "handkerchief", "tie", "hat", "brim",
        "trainer", "trilby", "cap", "stormwear", "backpack", "washbag", "mule", "liner"
    ]
    skip_keywords = [w for word in skip_base for w in (word, word + "s")]
    pattern = re.compile(r"\b(" + "|".join(skip_keywords) + r")\b", re.IGNORECASE)
    if pattern.search(product_name.lower()):
        print(f"Skipping product due to keyword match in title: {product_id}")
        return []
    skus = data['variants']
    temp = []
    for sku_value in skus:
        asset_id = sku_value.get("colourSwatchAssetId", "")
        color_id = asset_id.split("_")[-1] if "_" in asset_id else asset_id
        color_name = sku_value.get("colour", "").lower().strip()
        color_param = quote(color_name.lower().replace(" ", "-"))
        product_url = f"https://www.marksandspencer.com/{data['navigation']['seoUrl']}?color={color_param}"
        ski = sku_value.get("skus", [])
        raw_images = data.get("images", [])
        processed_images = []
        for img_url in raw_images:
            if "_EC_90" in img_url:
                processed_images.append({"url": img_url, "image_style": "s0"})
            else:
                processed_images.append({"url": img_url, "image_style": "s0"})
        for new_value in ski:
            current_prize = new_value['price']['currentPrice']
            old_prize = new_value['price'].get('previousPrice') or current_prize
            size_name = new_value['size']['primarySize']
            quantity = new_value['inventory']['quantity']
            availability = "in_stock" if quantity > 0 else "out_of_stock"
            entry = {
                "product_id": product,
                "sub_brand": brand_name,
                "gender": gender,
                "age_group": age_group,
                "age_range": age_range,
                "date_of_scraping": parse_launch_date(scraping_date),
                "url": product_url,
                "title": product_name.lower(),
                "description": description,
                "product_ref_code": reference_code,
                "color_id": f'{product_id}%{color_id}',
                "color_name": color_name,
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
                "images": processed_images,
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
    countries = ['UK']
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
