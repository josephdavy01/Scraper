import os
import json
import re
import html
from datetime import datetime
import traceback
from alert import raise_ticket

import traceback
from datetime import date, datetime

with open("alo_pid_remapping.json", "r", encoding="utf-8") as f:
    PID_MAP = json.load(f)

with open("alo_color_ids.json", "r", encoding="utf-8") as f:
    COLOR_MAPPING = json.load(f)

def get_folders(sub_folders, exclude_folder=None):
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
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def normalize_sku(sku: str) -> str:
                    sku = sku.strip().lower()
                    sku = re.sub(r'\d+r?$', '', sku)
                    m = re.match(r'([a-z0-9]+up)', sku)
                    if m:
                        return m.group(1)
                    m = re.match(r'([a-z0-9]+[mwupr])', sku)
                    if m:
                        return m.group(1)
                    return sku

def remap_gender(product_type):
    pt_lower = product_type.lower()
    if pt_lower.startswith("women"):
        return 'female'
    elif pt_lower.startswith("men"):
        return 'male'
    else:
        return 'unisex'

def get_image_list(node):
    return [
        {"url": img["node"]["url"], "image_style": f"s{idx}"}
        for idx, img in enumerate(node.get("images", {}).get("edges", []))
    ]

def get_color_id(color_name):
    return COLOR_MAPPING.get(color_name.lower(), f"cid_unknown")

def get_main_pid(sku: str, pid_map: dict) -> str:
    sku = sku.lower()
    base = re.match(r'([a-z0-9]+?[a-z]+)', sku)
    if base:
        base_sku = base.group(1)
    else:
        base_sku = sku
    for main_pid, sub_pids in pid_map.items():
        if base_sku in sub_pids:
            return main_pid
    return base_sku  

def create_individual_json(json_data, today_str):
    all_products = []
    errors = []
    if not json_data or not isinstance(json_data, dict):
        return [], ["Invalid JSON data"]
    
    for product in json_data.get("data", {}).get("products", {}).get("edges", []):
        node = product.get("node", {})
        product_type = node.get("productType", "")
        if product_type.lower().startswith("accessories"):
            # print(f"Skipping {product_type}")
            return [], [f"Skipping {product_type}"]

        title = node.get("title", "").lower().split('-')[0].strip()
        url = node.get("onlineStoreUrl") 
        images = get_image_list(node)
        gender = remap_gender(product_type)
        
        variants = node.get("variants", {}).get("edges", [])
        if not variants:
             errors.append("No variants found")

        for variant in variants:
            v_node = variant.get("node")
            current_sku = v_node.get("sku", "MISSING_SKU")
            if not v_node or not current_sku:
                errors.append(f"Missing node or SKU for variant")
                continue
            variant_url = v_node.get("onlineStoreUrl") or url
            if not variant_url:
                errors.append(f"Missing onlineStoreUrl for SKU {current_sku}")
                continue

            product_id = get_main_pid(current_sku, PID_MAP)
            prdt_id = "alo" + product_id
            size = next(
                (opt["value"] for opt in v_node["selectedOptions"]
                    if opt["name"].lower() == "size"), None
            )
            color_name = next(
                (opt["value"].strip().lower() for opt in v_node["selectedOptions"]
                    if opt["name"].lower() == "color"), None
            )
            colo_id = get_color_id(color_name) if color_name else "cid_unknown"

            if colo_id == "cid_unknown":
                errors.append(f"Unknown color ID for color '{color_name}' in SKU {current_sku}")
                continue

            sku = f"{prdt_id}%p{product_id}c{colo_id}s{size}"
            composition = next(
                (attr["value"] for attr in node.get("attributes", [])
                    if attr and attr.get("key") == "fabrication"), None
            )
            product_ref_code = v_node["id"].split("/")[-1]
            description_html = json_data.get("description", "")
            text_only = re.sub(r'<[^>]+>', '', description_html) if description_html else ""
            description = html.unescape(text_only)
            entry = {
                "product_id": prdt_id,
                "gender": gender,
                "age_group": ["adult"],
                "age_range": ["18y"],
                "date_of_scraping": parse_launch_date(today_str),
                "url": variant_url, 
                "title": title,
                "description": description,
                "product_ref_code": product_ref_code,
                "color_id": f'{prdt_id}%{colo_id}',
                "color_name": color_name,
                "color_ref_code": colo_id,
                "sku": sku,
                "size_name": size,
                "size_ref_code": None,
                "price": float(v_node["priceV2"]["amount"]),
                "launch_price": float(v_node["priceV2"]["amount"]),
                "availability": "in_stock" if v_node.get("availableForSale") else "out_of_stock",
                "demand": None,
                "origin": None,
                "composition": composition,
                "images": images
            }
            all_products.append(entry)
            
    if not all_products and not errors:
        errors.append("No valid products found (all filtered out or empty)")
        
    return all_products, errors

def process_jsons(today_str, country):
    all_country_products = []
    error_logs = []
    gender_folder = os.path.join(country, today_str, 'Json_data')
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
                    skus, errors = create_individual_json(data,today_str)
                    if skus:
                        all_country_products.extend(skus)
                    else:
                        print(f"Skipping {file} - {errors}")
                        error_logs.append({
                            "file": file,
                            "path": file_path,
                            "reasons": errors
                        })
                    
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()
                    error_logs.append({
                        "file": file,
                        "path": file_path,
                        "reasons": [str(e)]
                    })
    return all_country_products, error_logs

def save_country_data_to_json(countries, today_str, re_run=False):
    # If countries is a dict (like in master.py), we iterate keys. If list, iterate items.
    country_list = countries.keys() if isinstance(countries, dict) else countries

    for country in country_list:
        # Define output directory and file path first to check existence
        output_dir = os.path.join(country, today_str, 'Data')
        output_file = os.path.join(output_dir, f'{country}_data.json')
        
        if not re_run and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print(f"Data file {output_file} already exists and is not empty. Skipping processing for {country}.")
            continue

        print(f"Processing {country} apparel...")
        all_products, error_logs = process_jsons(today_str, country)
        
        os.makedirs(output_dir, exist_ok=True)

        if all_products:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_products, f, indent=4, default=datetime_serializer)
                print(f"Saved {len(all_products)} products to {output_file}")
            except Exception as e:
                print(f"Error saving data for {country}: {e}")
                raise_ticket("Step 6", "save_country_data_to_json", f"Error saving data for {country}: {str(e)}", country)
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
                raise_ticket("Step 6", "save_country_data_to_json", f"Error saving error logs for {country}: {str(e)}", country)

        print(f"Apparel data loading for {country} completed!")
