import os
import ast
import json
import traceback
import pandas as pd
from datetime import date, datetime

# Keys for categories that should be ignored
pop_keys = ['bags', 'belts', 'perfumes', 'sunglasses', 'accessories', 'shoes']

# --- Helper Functions -----------------------------------------------------

def datetime_serializer(obj):
    """Serialize datetime/date objects for JSON output."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def parse_launch_date(date_string):
    """Parse various date string formats into a datetime object."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {date_string}")


def get_images(media):
    """Convert a list of image URLs into the required dict structure."""
    images = []
    for url in media:
        if url:
            images.append({"url": url, "image_style": "s0"})
    return images


def get_url(handle, allurls):
    """Find the full product URL that contains the given handle."""
    for url in allurls:
        if handle in url:
            return url
    return None

# Global dictionaries populated at runtime
pdict = {}
cdict = {}

def get_pid(pid):
    """Map a Shopify product ID to the internal PID using pdict."""
    for internal_id, ids in pdict.items():
        if pid in ids:
            return internal_id
    return "0000000000000"

# --- Core Processing ------------------------------------------------------

def create_individual_json(allurls, today_str, data):
    """Transform a raw JSON product entry into one or more SKU dictionaries.

    Returns a list of product dictionaries ready for downstream consumption.
    """
    products = []
    product = data["product"]

    # Skip categories that are not apparel
    product_type = product.get("shopify_product_type", "").strip().lower()
    if any(key in product_type for key in pop_keys):
        return products

    # Resolve colour – some feeds store it as a stringified list
    try:
        colour = ast.literal_eval(product.get("color", ""))[0]
    except Exception:
        colour = product.get("color", "unknown") or "unknown"

    url = get_url(product.get("handle", ""), allurls)
    if not url or not colour:
        return products

    pid = "snh" + get_pid(product.get("shopify_product_id", ""))
    name = product.get("title", "").lower()
    description = product.get("short_description", "")
    colour_name = colour.lower().strip()
    cid = cdict.get(colour_name, "000")

    price = product.get("selling_price", 0)
    if not price:
        return products
    old_price = product.get("mrp", price) or price

    composition = product.get("material", "")
    images = get_images(product.get("images", []))

    sizes = data.get("sizes", {})
    size_inventory = sizes.get("size_to_inventory", {})
    variant_map = sizes.get("all_sizes_to_variant_id", {})

    for size_name, stock in size_inventory.items():
        availability = "in_stock" if stock else "out_of_stock"
        sku_suffix = "unknown"
        try:
            sku_suffix = str(variant_map[size_name][0])
        except Exception:
            pass

        entry = {
            "product_id": pid,
            "gender": "male",
            "age_group": ["adult"],
            "age_range": ["18y"],
            "date_of_scraping": parse_launch_date(today_str),
            "url": url,
            "title": name,
            "description": description,
            "product_ref_code": None,
            "color_id": f"{pid}%{cid}",
            "color_name": colour_name,
            "color_ref_code": None,
            "sku": f"{pid}%{sku_suffix}",
            "size_name": size_name,
            "size_ref_code": None,
            "price": price,
            "launch_price": old_price,
            "availability": availability,
            "demand": None,
            "composition": composition,
            "origin": None,
            "images": images,
        }
        products.append(entry)
    return products


def get_folders(base_path, exclude_files=None):
    """Return a list of sub‑folders in *base_path* excluding any files listed in *exclude_files*."""
    if not os.path.isdir(base_path):
        return []
    exclude_files = set(exclude_files or [])
    return [name for name in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, name)) and name not in exclude_files]


def process_jsons(today_str, country):
    """Walk through the JSON data for *country* and return aggregated products and log data.

    Expected layout:
    {country}/
        {today_str}/
            Json_data/   <-- raw product JSON files
            Item_urls/   <-- JSON file with all product URLs
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
    for root, _, files in os.walk(data_root):
        for filename in files:
            if not filename.lower().endswith('.json'):
                continue
            file_path = os.path.join(root, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
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

