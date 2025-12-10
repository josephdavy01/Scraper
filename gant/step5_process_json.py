import os
import json
import html
from datetime import datetime, date

# ---------------- LOAD MAPPINGS ----------------
try:
    with open('gant_pid_remapping.json', 'r', encoding='utf-8') as f:
        PID_MAP = json.load(f)
except Exception:
    PID_MAP = {}

try:
    with open('gant_cid_remapping.json', 'r', encoding='utf-8') as f:
        COLOR_MAPPING = json.load(f)
except Exception:
    COLOR_MAPPING = {}

# ---------------- UTILITIES ----------------

def parse_launch_date(date_string):
    format_string_with_ms = '%Y-%m-%dT%H:%M:%S.%fZ'
    format_string_without_ms = '%Y-%m-%dT%H:%M:%SZ'
    format_string_date_only = '%Y-%m-%d'
    format_string_with_ms_no_tz = '%Y-%m-%d %H:%M:%S.%f'

    for fmt in [format_string_with_ms, format_string_without_ms,
                format_string_date_only, format_string_with_ms_no_tz]:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue

    raise ValueError(f"Invalid date format: {date_string}")

def get_image_list(images):
    """Convert image dicts to expected output. Expects list of dicts with 'src' and optional 'position'."""
    out = []
    if not images:
        return out
    if len(images) == 1:
        src = images[0].get('src') if isinstance(images[0], dict) else images[0]
        if src:
            out.append({"url": src, "image_style": "n_f_f_c"})
        return out
    for img in images:
        if isinstance(img, dict):
            src = img.get('src')
            pos = str(img.get('position', '0'))
        else:
            src = img
            pos = '0'
        style = f"s{pos}" if pos.isdigit() and 1 <= int(pos) <= 9 else "s0"
        if src:
            out.append({"url": src, "image_style": style})
    return out

def normalize_color(color):
    if not color:
        return ''
    return str(color).replace("'", "").strip().lower()

def get_color_id(color_name):
    if not color_name:
        return 'cid_unknown'
    return COLOR_MAPPING.get(color_name.lower(), 'cid_unknown')

def get_main_pid_from_handle(handle):
    """Extract a numeric id piece from handle and prefix with gnt; fallback None."""
    if not handle:
        return None
    handle = handle.replace('_', '-')
    for part in handle.split('-'):
        if part.isdigit() and len(part) > 3:
            return f"gnt{part}"
    return None

# ---------------- PARSER ----------------

def create_individual_json(gender, product, today_str_iso):
    """
    product: dict loaded from single product JSON file
    returns: list of product entries
    """
    if not product or not isinstance(product, dict):
        return []

    handle = product.get('handle')
    if not handle:
        return []

    product_id = get_main_pid_from_handle(handle)
    if not product_id:
        return []

    url = f"https://gant.ae/products/{handle}"
    title = (product.get('title') or "").lower()
    desc_html = product.get('body_html') or ""
    description = html.unescape(__import__('re').sub(r"<[^>]+>", "", desc_html))
    images = get_image_list(product.get('images', []))
    tags = [t.lower() for t in product.get('tags', [])] if product.get('tags') else []
    # skip accessories
    if any(t in tags for t in ('accessories', 'accessory')):
        return []

    variants = product.get('variants', []) or []
    entries = []
    for var in variants:
        sku_raw = var.get('sku') or ''
        if not sku_raw:
            continue

        color_name = normalize_color(var.get('option1', 'unknown'))
        size_name = var.get('option2', '').strip() or None
        color_id = get_color_id(color_name)
        if color_id == 'cid_unknown':
            # skip unknown colors in minimal version
            continue

        try:
            price = float(var.get('price', 0))
        except Exception:
            price = 0.0
        try:
            launch_price = float(var.get('compare_at_price', price))
        except Exception:
            launch_price = price

        availability = 'in_stock' if var.get('available') else 'out_of_stock'
        final_sku = f"{product_id}%{sku_raw}"

        entry = {
            "product_id": product_id,
            "gender": (gender or 'unisex').strip().lower(),
            "age_group": ["adult"],
            "age_range": ["18y"],
            "date_of_scraping": parse_launch_date(today_str_iso).isoformat() if parse_launch_date(today_str_iso) else None,
            "url": url,
            "title": title,
            "description": description,
            "product_ref_code": None,
            "color_id": f"{product_id}%{color_id}",
            "color_name": color_name,
            "color_ref_code": color_id,
            "sku": final_sku,
            "size_name": size_name,
            "size_ref_code": None,
            "price": price,
            "launch_price": launch_price,
            "availability": availability,
            "demand": None,
            "origin": None,
            "composition": None,
            "images": images,
        }
        entries.append(entry)

    return entries

# ---------------- PROCESS FILES & SAVE ----------------

def process_jsons_and_save(countries, today_str=None, re_run=False):
    """
    countries: iterable or dict keys. Example: ['UAE'] or {'UAE': 'https://gant.ae/'}
    """
    if today_str is None:
        today_str = date.today().strftime('%Y-%m-%d')

    country_list = countries.keys() if isinstance(countries, dict) else countries

    for country in country_list:
        base_folder = os.path.join(country, today_str, "Json_data")
        if not os.path.exists(base_folder):
            print(f"[SKIP] No data folder for {country}: {base_folder}")
            continue

        all_products = []
        # expected structure: Json_data/<gender>/<category>/*.json
        for gender in os.listdir(base_folder):
            gender_path = os.path.join(base_folder, gender)
            if not os.path.isdir(gender_path):
                continue
            for category in os.listdir(gender_path):
                cat_path = os.path.join(gender_path, category)
                if not os.path.isdir(cat_path):
                    continue
                for fname in os.listdir(cat_path):
                    fpath = os.path.join(cat_path, fname)
                    if not os.path.isfile(fpath) or not fname.lower().endswith('.json'):
                        continue
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        entries = create_individual_json(gender, data, today_str)
                        if entries:
                            all_products.extend(entries)
                    except Exception as e:
                        # minimal approach: print file and continue
                        print(f"[ERROR] {fpath}: {e}")
                        continue

        output_dir = os.path.join(country, today_str, "Final_json")
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"data.json")

        if not re_run and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print(f"[SKIP] {output_file} exists and non-empty. Use re_run=True to overwrite.")
            continue

        if all_products:
            try:
                with open(output_file, 'w', encoding='utf-8') as out_f:
                    json.dump(all_products, out_f, indent=4, ensure_ascii=False)
                print(f"[SAVED] {len(all_products)} products -> {output_file}")
            except Exception as e:
                print(f"[ERROR SAVING] {output_file}: {e}")
                if os.path.exists(output_file):
                    os.remove(output_file)
                    print(f"[CLEANUP] Removed corrupted file: {output_file}")
        else:
            print(f"[NO DATA] No products found for {country} on {today_str}")

# ---------------- RUNNER ----------------

def run_gant_processing(today_str=None, countries=None, re_run=False):
    """Wrapper used by master.py to process JSON data.
    Calls process_jsons_and_save with appropriate defaults.
    """
    if countries is None:
        countries = {'UAE': 'https://gant.ae/'}
    process_jsons_and_save(countries, today_str, re_run)

if __name__ == "__main__":
    # Direct execution for debugging
    run_gant_processing()
