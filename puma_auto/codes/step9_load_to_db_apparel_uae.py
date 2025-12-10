import os
import json
from datetime import date, datetime
from urllib.parse import urljoin
import pymongo
import re

base_url = 'https://ae.puma.com/'

def parse_launch_date(date_string: str) -> datetime:
    try:
        return datetime.strptime(date_string, '%Y-%m-%d')
    except ValueError:
        return None

def label_map_from_attributes(item, code):
    mapping = {}
    for attr in (item or {}).get('attributes', []) or []:
        if attr.get('attribute_code') == code and isinstance(attr.get('attribute_options'), list):
            for opt in attr['attribute_options']:
                v = str(opt.get('value', '')).strip()
                l = str(opt.get('label', '')).strip()
                if v and l:
                    mapping[v] = l
    return mapping

def lookup_label(value, mapping, fallback=None):
    if value is None:
        return fallback
    return mapping.get(str(value), fallback)

def get_min_prices(minimum_price_dict):
    if not isinstance(minimum_price_dict, dict):
        return None, None
    fp = minimum_price_dict.get('final_price') or {}
    rp = minimum_price_dict.get('regular_price') or {}
    return fp.get('value'), rp.get('value')


def pick_media_url(entry):
    if not isinstance(entry, dict):
        return None
    for key in ('large', 'base', 'thumbnail'):
        node = entry.get(key)
        if isinstance(node, dict) and node.get('url'):
            url = node['url']
            if 'fallback/dummy' not in url:
                return url
    for key in ('large', 'base', 'thumbnail', 'file'):
        v = entry.get(key)
        if isinstance(v, str) and v.startswith('http') and 'fallback/dummy' not in v:
            return v
    return None


def collect_images(vproduct, item):
    images = []
    for entry in (vproduct or {}).get('media_gallery_entries', []) or []:
        url = pick_media_url(entry)
        if url:
            images.append({"url": url, "image_style": "s0"})
    for key in ('image', 'small_image', 'thumbnail'):
        node = (vproduct or {}).get(key)
        if isinstance(node, dict) and node.get('url'):
            url = node['url']
            if 'fallback/dummy' not in url:
                images.append({"url": url, "image_style": "s0"})
    seen, deduped = set(), []
    for img in images:
        u = img['url']
        if u not in seen:
            seen.add(u)
            deduped.append(img)
    style_updated = False
    for img in deduped:
        url = img['url']
        parts = url.split('/fnd/')
        if len(parts) < 2:
            continue 
        before_fnd = parts[0].split('/')[-1]
        if before_fnd.isdigit():
            img['image_style'] = 'n_f_f_c'
            style_updated = True
            continue 
        after_fnd = parts[1].split('/')[0]
        if after_fnd.isdigit():
            img['image_style'] = 'n_f_f_c'
            style_updated = True
    if not style_updated and len(deduped) > 2:
        deduped[2]['image_style'] = 'n_f_f_c'
    return deduped

def remove_html(description):
    if not description:
        return ""
    clean_desc = re.sub(r'<[^>]+>', '', description)
    clean_desc = ' '.join(clean_desc.split())
    clean_desc = clean_desc.replace('&nbsp;', ' ').replace('&amp;', '&')
    return clean_desc.strip()

def extract_material_composition(product_dict):
    raw_value = None
    for attr in (product_dict or {}).get("attributes", []):
        if attr.get("attribute_code") == "material_composition" and attr.get("attribute_value"):
            raw_value = attr["attribute_value"]
            break
    cleaned_text = re.sub(r'<[^>]+>', ' ', raw_value)
    cleaned_text = ' '.join(cleaned_text.split()).replace('&nbsp;', ' ').replace('&amp;', '&').strip()
    return  cleaned_text

def extract_gender(categories, title):
    text = ' '.join([cat.get('name', '').lower() for cat in categories])
    full_text = text + ' ' + title.lower()
    tokens = set(re.findall(r'\b\w+\b', full_text))  # Tokenize into words
    if any(word in {'kid', 'kids', 'youth', 'infant', 'toddler', 'baby'} for word in tokens):
        return 'kids'
    if 'unisex' in tokens:
        return 'unisex'
    has_men = 'men' in tokens or 'mens' in tokens
    has_women = any(word in {'woman', 'women', 'womens'} for word in tokens)
    if has_men and has_women:
        return 'unisex'
    if has_men:
        return 'male'
    if has_women:
        return 'female'
    return 'unisex'

def get_age_group(gender):
    gender = gender.lower()
    if gender in ['female', 'women', 'male', 'men']:
        return ['adult']
    if gender in ['kids', 'youth']:
        return ['kids']
    return ['adult']

def get_age_range(gender):
    gender = gender.lower()
    if gender in ['female', 'women', 'male', 'men']:
        return ['18y']
    if gender in ['kids', 'youth']:
        return ['1y', '17y']
    return ['18y']

def is_apparel(item):
    for a in (item or {}).get('attributes', []) or []:
        if a.get('attribute_code') == 'product_division' and isinstance(a.get('attribute_options'), list) and a['attribute_options']:
            label = str(a['attribute_options'][0].get('label') or '').strip().lower()
            if label == 'apparel':
                return True
    return False

def get_attr_value(product, code):
    for a in (product or {}).get('attributes', []) or []:
        if a.get('attribute_code') == code:
            return a.get('attribute_value')
    return product.get(code)

def create_individual_json(today_str, json_data):
    all_products = []
    items = (((json_data or {}).get('data') or {}).get('products') or {}).get('items') or []
    if not items or not isinstance(items, list):
        return []
    item = items[0]
    
    if not is_apparel(item):
        return []
    
    product_id = 'pum' + str(item.get('sku', '')).split('_')[0].strip()
    name = (item.get('name') or '').strip().lower()
    if not product_id or not name:
        return []
    main_sku = item.get('sku', '')
    if '_' not in main_sku:
        return []
    
    cid = main_sku.split('_')[1].strip()
    item_categories = item.get('categories') or []
    gender = extract_gender(item_categories,name)
    if gender =='kids':
        return []
    age_group = get_age_group(gender)
    age_range = get_age_range(gender)
    
    color_map = label_map_from_attributes(item, 'color')
    size_map = label_map_from_attributes(item, 'size')
    product_url = urljoin(base_url, item.get('url')) if item.get('url') else None  # Use provided URL (includes color)
    min_price = (((item or {}).get('price_range') or {}).get('minimum_price')) or {}
    price, old_price = get_min_prices(min_price)
    raw_description = (item.get("description") or {}).get("html") or ""
    full_description = remove_html(raw_description)
    
    variants = item.get('variants') or []
    main_style = item.get('sku') or get_attr_value(item, 'style_number') or ''
    
    seen_variant_skus = set()
    
    kids_size_pattern = re.compile(r"^\d{1,2}(-\d{1,2})?[my]$")
    for variant in variants:
        vproduct = variant.get('product', variant)
        v_style = get_attr_value(vproduct, 'style_number') or vproduct.get('style_number')
        if not v_style or v_style != main_style:
            continue
        v_sku_for_dedupe = vproduct.get('sku') or str(vproduct.get('id'))
        if v_sku_for_dedupe in seen_variant_skus:
            continue
        seen_variant_skus.add(v_sku_for_dedupe)
        salable_qty = vproduct.get('salable_qty')
        stock = vproduct.get('stock_status') or ''
        if salable_qty is not None:
            availability = stock.strip().lower() if stock else None
            if availability == 'in_stock':
                availability = 'in_stock'
            elif availability == 'out_of_stock':
                availability = 'out_of_stock'
        else:
            availability = 'in_stock' if (isinstance(salable_qty, (int, float)) and salable_qty > 0) else 'out_of_stock'
            
        variant_color_value = get_attr_value(vproduct, 'color')
        composition = extract_material_composition(vproduct)
        images = collect_images(vproduct, item)  # Updated to collect only variant images
        cname = lookup_label(variant_color_value, color_map, fallback=(vproduct.get('color_description') or None))
        size_code = get_attr_value(vproduct, 'size')
        sizename = lookup_label(size_code, size_map, fallback=None)
        sku = vproduct.get('sku')
        variant_min_price = (((vproduct or {}).get('price_range') or {}).get('minimum_price')) or {}
        variant_price, variant_old_price = get_min_prices(variant_min_price)
        final_price = variant_price if variant_price is not None else price
        final_old_price = variant_old_price if variant_old_price is not None else old_price
        
        size_clean = sizename.lower().strip()
        if kids_size_pattern.match(size_clean):
            print(f"Skipping product '{sizename}' because it has a kids' size: {sizename}")
            return []
        
        entry = {
            "product_id": product_id,
            "gender": gender,
            "age_group": age_group,
            "age_range": age_range,
            "date_of_scraping": parse_launch_date(today_str),
            "url": product_url,
            "title": name,
            "description": full_description,
            "product_ref_code": None,
            "color_id": f"{product_id}%{cid}",
            "color_name": cname,
            "color_ref_code": main_style.split('_')[-1] if '_' in main_style else main_style,
            "sku": f"{product_id}%{sku}",
            "size_name": sizename,
            "size_ref_code": None,
            "price": final_price,
            "launch_price": final_old_price,
            "availability": availability,
            "demand":None,
            "composition":composition,
            "origin": None,
            "images": images  
        }
        all_products.append(entry)
    return all_products

def read_json_file(file_path):
    last_err = None
    for enc in ('utf-8', 'utf-16'):
        try:
            with open(file_path, 'r', encoding=enc) as jf:
                return json.load(jf)
        except Exception as e:
            last_err = e
    raise last_err if last_err else ValueError("Failed to read JSON")

def process_jsons(today_str, country, collection):
    base_path = os.path.join(country, 'Data', today_str, 'Json_data')
    if not os.path.exists(base_path):
        print(f"Directory {base_path} does not exist.")
        return
    genders = [g for g in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, g))]
    for gender in genders:
        gender_folder = os.path.join(base_path, gender)
        categories = [c for c in os.listdir(gender_folder) if os.path.isdir(os.path.join(gender_folder, c))]
        for category in categories:
            category_folder = os.path.join(gender_folder, category)
            files = [f for f in os.listdir(category_folder) if f.endswith('.json')]
            for file in files:
                file_path = os.path.join(category_folder, file)
                print(f"Processing file: {file_path}")
                try:
                    data = read_json_file(file_path)
                    skus = create_individual_json(today_str, data)
                    if skus:
                        collection.insert_many(skus)
                        print(f'Processed {len(skus)} variants for current color')
                        for sku in skus:
                            print(f'Product_id: {sku["product_id"]}, SKU: {sku["sku"]}, Size: {sku["size_name"]}')
                    else:
                        print(f"No SKUs generated for file: {file_path}")
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")


if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-06' 
    

    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']
    countries = ['UAE']
    for country in countries:
        collection = db[f'crawler_sink_puma_{country.lower()}']
        process_jsons(today_str, country, collection)
    client.close()
