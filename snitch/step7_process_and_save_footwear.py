import os
import ast
import json
import traceback
import pandas as pd
from datetime import date, datetime
from bs4 import BeautifulSoup

pop_keys = ['bags', 'belts', 'perfumes', 'sunglasses', 'accessories']

# --- HELPER: Date Serializer for JSON Output ---
def datetime_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def extract_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    key_map = {
        'sole material': 'sole_material',
        'upper material': 'upper_material',
        'closure type': 'closure_type',
        'occasion': 'occasion'
    }
    extracted = {}

    try:
        for b in soup.find_all('b'):
            key_raw = b.get_text(strip=True).lower()
            mapped_key = key_map.get(key_raw)
            if mapped_key:
                next_node = b.next_sibling
                value = None
                while next_node:
                    if isinstance(next_node, str):
                        value = next_node.strip().lstrip(':').strip()
                        if value:
                            break
                    elif next_node.name == 'br':
                        break
                    next_node = next_node.next_sibling
                if value:
                    extracted[mapped_key] = value

        return (
            extracted.get('sole_material'),
            extracted.get('upper_material'),
            extracted.get('closure_type'),
            extracted.get('occasion')
        )

    except Exception as e:
        print(f"Error extracting info: {e}")
        traceback.print_exc()
        return None, None, None, None
    

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

def get_images(media):
    images = []
    for url in media:
        if url:  
            temp = {
                "url": url,
                "image_style": 's0'
            }
            images.append(temp)
    return images

# Get url
def get_url(handle, allurls):
    for url in allurls:
        if handle in url:
            return url

# Get Pid
def get_pid(pid):
    # Uses global pdict loaded in main
    for i, j in pdict.items():
        if pid in j:
            return i
    return '0000000000000'

# Function to create individual JSON objects for each SKU
def create_individual_json(allurls, today_str, data):
    all_products = []
    product = data['product']

    product_type = product['shopify_product_type'].strip().lower()
    if any(key in product_type for key in pop_keys):
        return all_products
    
    if product_type == 'shoes':
        sizes = data['sizes']
        color_raw = product.get('color')
        if not color_raw:
            print(f"Skipping product - color is None or empty for {product.get('title')}")
            return all_products

        try:
            # Handle both list string and plain string if needed, though eval expects list string
            try:
                color_list = ast.literal_eval(color_raw)
                if not color_list:
                    print(f"Skipping product - empty color list for {product.get('title')}")
                    return all_products
                color = color_list[0]
            except:
                # Fallback if color is just a string
                color = color_raw
        except Exception as e:
            print(f"Skipping product - color parse error for {product.get('title')}: {e}")
            return all_products

        url = get_url(product['handle'], allurls)
        if url and color:
            pid = 'snh' + get_pid(product['shopify_product_id'])
            name = product['title'].lower()
            description_html = product['description']

            sole_material,upper_material,closure_type,occasion = extract_info(description_html)

            soup = BeautifulSoup(description_html, 'html.parser')
            description = soup.get_text(separator=' ', strip=True)
            cname = color.lower().strip()
            
            #Safe get for cdict
            cid = cdict.get(cname, "000")
            
            price = product['selling_price']
            oldprice = product['mrp']
            if oldprice == 0 or oldprice == None:
                oldprice = price
            
            images = get_images(product['images'])
            
            for sname, stock in sizes['size_to_inventory'].items():
                if stock == 0:
                    availability = 'out_of_stock'
                else:
                    availability = 'in_stock'
                
                try:
                    sku_suffix = str(sizes['all_sizes_to_variant_id'][sname][0])
                except:
                    sku_suffix = "unknown"

                entry = {
                    "product_id": pid,
                    "sub_brand": None,
                    "gender": 'male',
                    "age_group": ['adult'],
                    "age_range": ['18y'],
                    "date_of_scraping": parse_launch_date(today_str),
                    "url": url,
                    "title": name,
                    "description": description,
                    "product_ref_code" : None,
                    "color_id": f'{pid}%{cid}',
                    "color_name": cname,
                    "color_ref_code" : None,
                    "sku": f'{pid}%{sku_suffix}',
                    "size_name": sname,
                    "size_ref_code" : None,
                    "price": price,
                    "launch_price": oldprice,
                    "availability": availability,
                    "sole_material": sole_material,
                    "upper_material": upper_material,
                    "closure_type": closure_type,
                    "toe_type": None,
                    "heel_type": None,
                    "weight": None,
                    "heel_to_toe_drop": None,
                    "occasion": occasion,
                    "origin": None,
                    "images": images
                }
                all_products.append(entry)

    return all_products

def process_jsons_footwear(today_str, country):
    """
    Walk through the Json_data directory for *country*, process footwear JSONs,
    and return aggregated products and log data.
    """
    all_products = []

    # Load all product URLs and flatten nested structure
    urls_path = os.path.join(country, today_str, "Item_urls", f"{country}_product_links.json")
    all_urls = []
    if os.path.exists(urls_path):
        with open(urls_path, "r", encoding="utf-8") as f:
            url_data = json.load(f)
            # Flatten nested structure: {"men": {"Category": [urls]}}
            for gender, categories in url_data.items():
                for category, urls in categories.items():
                    all_urls.extend(urls)
    else:
        print(f"Warning: URL file not found at {urls_path}")
        return [], []

    # Walk the Json_data directory recursively
    data_root = os.path.join(country, today_str, "Json_data")
    if not os.path.exists(data_root):
        print(f"Warning: Data root not found at {data_root}")
        return [], []

    for root, _, files in os.walk(data_root):
        for filename in files:
            if not filename.lower().endswith('.json'):
                continue
            file_path = os.path.join(root, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Use the existing create_individual_json function
                products = create_individual_json(all_urls, today_str, data)
                all_products.extend(products)
                
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                traceback.print_exc()

    return all_products, all_products

def log_sku_details_to_csv(data, filepath):
    """Save the list of product dictionaries to a CSV file."""
    if not data:
        return
    try:
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding='utf-8')
    except Exception as e:
        print(f"Error saving CSV log: {e}")

