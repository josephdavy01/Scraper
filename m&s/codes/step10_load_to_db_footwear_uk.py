import json
from datetime import datetime
import os
import pymongo
import re
from urllib.parse import quote
import unicodedata

def parse_launch_date(date_string):
    """Parse date string in various formats to datetime"""
    for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%d']:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    return None

def normalize_text(text):
    if not text:
        return ""
    # Lowercase, strip spaces, normalize unicode
    return unicodedata.normalize("NFKD", text).strip().lower()

def process_data(json_data, scraping_date, gender):
    attrs = json_data.get("attributes", {})
    product_id = attrs.get("strokeId", "")
    product = product_id
    brand_name = attrs.get("brand", "").strip().lower()
    age_group = ['adult']
    age_range = ['18y']
    reference_code = attrs.get("strokeId", "")
    product_name = attrs.get("masterProductDescription", "").strip()
    description = attrs.get("masterAspirationalText", "")

    footwear_keywords = ["shoe", "boot", "sandal", "trainer", "sneaker", "loafer", "pump", "slipper"]
    expanded_keywords = []
    for kw in footwear_keywords:
        expanded_keywords.append(kw)
        expanded_keywords.append(kw + "s")

    product_def = normalize_text(json_data.get("attributes", {}).get("productDefinition"))

    if not any(word in product_def for word in expanded_keywords):
        print(f"Skipping non-footwear: {product_id} {product_name} ({repr(product_def)})")
        return []


    heel_to_toe_drop = None
    inline_bullet = attrs.get("inlineReferenceBullet1", "")
    match = re.search(r"(?:item\s+details#)?heel\s+height.*?:\s*(\d+\s*mm)", inline_bullet, re.IGNORECASE)
    if match:
        heel_to_toe_drop = match.group(1).strip()

    upper_material = json_data.get("upper_material", "")
    sole_material = json_data.get("sole_material", "")

    skus = json_data.get("variants", [])
    temp = []

    for sku_value in skus:
        asset_id = sku_value.get("colourSwatchAssetId", "")
        color_id = asset_id.split("_")[-1] if "_" in asset_id else asset_id
        color_name = sku_value.get("colour", "").lower().strip()
        color_param = quote(color_name.replace(" ", "-").lower())
        product_url = f"https://www.marksandspencer.com/{json_data.get('navigation', {}).get('seoUrl', '')}?color={color_param}"

        # Images
        raw_images = json_data.get("images", [])
        processed_images = []
        for img_url in raw_images:
            image_style = "s0" if re.search(r"EC_90", img_url) else "s0"
            processed_images.append({"url": img_url, "image_style": image_style})

        for new_value in sku_value.get("skus", []):
            sku = new_value.get("id", "")
            current_price = new_value.get("price", {}).get("currentPrice")
            old_price = new_value.get("price", {}).get("previousPrice") or current_price
            size_name = new_value.get("size", {}).get("primarySize", "")
            quantity = new_value.get("inventory", {}).get("quantity", 0)
            availability = "in_stock" if quantity > 0 else "out_of_stock"

            entry = {
                "product_id": product,
                "gender":gender.lower(),
                "sub_brand": brand_name,
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
                "price": current_price,
                "launch_price": old_price,
                "availability": availability,
                "sole_material": sole_material,
                "upper_material": upper_material,
                "closure_type":None,
                "toe_type": None,
                "heel_type": None,
                "weight": None,
                "occasion": None,
                "heel_to_toe_drop": heel_to_toe_drop,
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
        if single_day:
            folders_to_process = [single_day] 
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
            db = client['footwear_analytics']
            collection = db[f'crawler_sink_marknspencer_group_{country.lower()}_footwear']
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

