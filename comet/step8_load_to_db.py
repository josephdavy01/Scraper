import os
import re
import json
import pymongo
import traceback
from datetime import date, datetime, timezone
from typing import List, Tuple

EXCLUDED_KEYWORDS = [
    "gift card", "membership", "members"
]

PRODUCT_ID_MAP_PATH = "product_id_map.json"
COLOR_ID_MAP_PATH = "color_id_map.json"


def is_excluded_product(title: str) -> bool:
    if not title:
        return False
    title_lower = title.lower()
    for word in EXCLUDED_KEYWORDS:
        pattern = r'\b' + re.escape(word) + r's?\b'
        if re.search(pattern, title_lower):
            return True
    return False


def parse_launch_date(today_str: str) -> datetime:
    dt = datetime.strptime(today_str, "%Y-%m-%d")
    dt = dt.replace(tzinfo=timezone.utc)
    return dt


def get_image_style(image_list: List[str]) -> List[dict]:
    styled_images = []
    for img in image_list:
        if not img:
            continue
        url = img
        # ensure scheme
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://www.wearcomet.com" + url
        # determine style
        low = url.lower()
        if "front" in low:
            styled_images.append({"url": url, "image_style": "n_f_f_c"})
        else:
            styled_images.append({"url": url, "image_style": "s0"})
    return styled_images


def _normalize_key(s: str) -> str:
    """
    Normalize string for map lookups: strip, collapse whitespace, title-case certain tokens (v2 -> V2).
    """
    if s is None:
        return ""
    s = s.strip()
    # collapse multiple spaces
    s = re.sub(r'\s+', ' ', s)
    # convert common 'v2' to 'V2' etc.
    s = re.sub(r'\bv(\d+)\b', lambda m: "V" + m.group(1), s, flags=re.IGNORECASE)
    return s.strip()


def load_product_map(path: str) -> Tuple[dict, dict]:
    """
    Returns (id_map, title_map):
      - id_map: normalized_key -> id
      - title_map: normalized_key -> original_key (canonical title string present in json)
    """
    if not os.path.exists(path):
        return {}, {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            id_map = {}
            title_map = {}
            for k, v in data.items():
                nk = _normalize_key(k).lower()
                id_map[nk] = v
                title_map[nk] = k  # keep original key as canonical title
            return id_map, title_map
    except Exception:
        return {}, {}


def load_json_map(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            norm = {}
            for k, v in data.items():
                nk = _normalize_key(k).lower()
                norm[nk] = v
            return norm
    except Exception:
        return {}


# Load maps once
PRODUCT_ID_MAP, PRODUCT_TITLE_MAP = load_product_map(PRODUCT_ID_MAP_PATH)
COLOR_ID_MAP = load_json_map(COLOR_ID_MAP_PATH)


def find_product_id_and_title(product_type: str, title: str, handle: str) -> Tuple[str, str]:
    """
    Determine product_id and canonical_title using rules:
      - Try normalized candidates extracted from title and handle against PRODUCT_ID_MAP
      - If matched return (id, canonical_title_from_map)
      - Fallback to product_type normalized match
      - If nothing found return ("000000", title_fallback)
    """
    candidates = []

    if title:
        t = title.strip()
        parts = re.split(r'\s+', t)
        if len(parts) >= 2:
            # try first two tokens as candidate (covers "Aeon V2", "X Lows")
            candidates.append(f"{parts[0]} {parts[1]}")
            candidates.append(parts[0])
        else:
            candidates.append(parts[0])

    if handle:
        h = handle.replace('-', ' ')
        h_parts = re.split(r'\s+', h)
        if len(h_parts) >= 2:
            candidates.append(f"{h_parts[0]} {h_parts[1]}")
            candidates.append(h_parts[0])
        else:
            candidates.append(h_parts[0])

    if product_type:
        candidates.append(product_type)

    # try candidates
    for cand in candidates:
        nk = _normalize_key(cand).lower()
        if nk in PRODUCT_ID_MAP:
            return PRODUCT_ID_MAP[nk], PRODUCT_TITLE_MAP.get(nk, cand)

    # try direct normalized title
    if title:
        nk = _normalize_key(title).lower()
        if nk in PRODUCT_ID_MAP:
            return PRODUCT_ID_MAP[nk], PRODUCT_TITLE_MAP.get(nk, title)

    # try product_type
    if product_type:
        nk = _normalize_key(product_type).lower()
        if nk in PRODUCT_ID_MAP:
            return PRODUCT_ID_MAP[nk], PRODUCT_TITLE_MAP.get(nk, product_type)

    # fallback: return default id and title fallback (prefer using title if present else handle)
    fallback_title = title if title else (handle.replace('-', ' ') if handle else '')
    return "000000", fallback_title


def find_color_id(color_name: str) -> str:
    if not color_name:
        return ""
    nk = _normalize_key(color_name).lower()
    return COLOR_ID_MAP.get(nk, "")


def safe_size_token(size: str) -> str:
    if not size:
        return ""
    s = re.sub(r'[^A-Za-z0-9]', '', size)
    return s.upper()


def cents_to_unit(value) -> float:
    if value is None:
        return None
    try:
        return float(value) / 100.0
    except Exception:
        try:
            return float(str(value).replace(',', '')) / 100.0
        except Exception:
            return None


def clean_html_to_text(html: str) -> str:
    if not html:
        return ""
    # remove all HTML tags
    text = re.sub(r'<[^>]+>', '', html)
    # collapse multiple whitespace and newlines
    text = re.sub(r'[\r\n]+', '\n', text)
    # trim each line and remove empty lines
    parts = [p.strip() for p in text.split('\n') if p.strip()]
    # join with " | "
    return " | ".join(parts)


def create_individual_json(today_str: str, json_data: dict) -> List[dict]:
    all_products = []
    if not json_data or not isinstance(json_data, dict):
        return []

    url = json_data.get("url", "")
    handle = json_data.get("handle", "")
    title_raw = json_data.get("title", "") or json_data.get("name", "")

    if is_excluded_product(title_raw or handle):
        print(f"Skipping - excluded item ({title_raw or handle})")
        return []

    product_type = json_data.get("type", "")

    # determine product id and canonical title
    product_id, canonical_title = find_product_id_and_title(product_type, title_raw, handle)
    if product_id == "000000":
        print(f"Skipping - excluded item ({product_id})")
        return []

    # set output title as canonical title from map (lowercase) — fallback to canonical_title
    output_title = (canonical_title or title_raw or handle).lower()

    # description cleaning (remove tags like <br>, <p>, etc.)
    raw_description = json_data.get("description", "") or json_data.get("content", "") or ""
    description = clean_html_to_text(raw_description)

    # images
    images_raw = json_data.get("images", []) or json_data.get("image", []) or []
    images = get_image_style(images_raw)

    # price logic
    price_val = json_data.get("price")
    compare_at = json_data.get("compare_at_price")
    price_unit = None
    launch_price_unit = None
    if price_val is not None:
        if compare_at is None or compare_at == 0:
            price_unit = cents_to_unit(price_val)
            launch_price_unit = price_unit
        else:
            price_unit = cents_to_unit(price_val)
            launch_price_unit = cents_to_unit(compare_at)
    else:
        variants = json_data.get("variants", [])
        if variants:
            vprice = variants[0].get("price")
            vcompare = variants[0].get("compare_at_price")
            if vprice is not None:
                if not vcompare:
                    price_unit = cents_to_unit(vprice)
                    launch_price_unit = price_unit
                else:
                    price_unit = cents_to_unit(vprice)
                    launch_price_unit = cents_to_unit(vcompare)

    if price_unit is None:
        print(f"Skipping {handle} - price missing")
        return []

    prdt_id = str(product_id)
    product_id_str = 'com' + str(product_id)

    for var in json_data.get("variants", []):
        option1 = var.get("option1") or (var.get("options") and var.get("options")[0] if var.get("options") else None)
        option2 = var.get("option2") or (var.get("options") and (var.get("options")[1] if len(var.get("options")) > 1 else None) if var.get("options") else None)

        if not option1 and var.get("public_title"):
            parts = re.split(r'\s*/\s*', var.get("public_title"))
            option1 = parts[0] if parts else option1
        if not option2 and var.get("public_title"):
            parts = re.split(r'\s*/\s*', var.get("public_title"))
            option2 = parts[1] if len(parts) > 1 else option2

        color_name = option1.strip() if isinstance(option1, str) else ""
        size_name = str(option2).strip() if option2 is not None else ""

        cid = find_color_id(color_name)
        size_token = safe_size_token(size_name) or str(var.get("id", ""))

        availability = "in_stock" if var.get("available", False) else "out_of_stock"

        sku = f"{product_id_str}%p{prdt_id}c{cid}s{size_token}"

        entry = {
            "product_id": product_id_str,
            "sub_brand": None,
            "gender": "unisex",
            "age_group": ['adult'],
            "age_range": ['18y'],
            "date_of_scraping": parse_launch_date(today_str),
            "url": url if url else (json_data.get("@id") or ""),
            "title": output_title,
            "description": description,
            "product_ref_code": prdt_id,
            "color_id": f"{product_id_str}%{cid}" if cid else None,
            "color_name": color_name.lower(),
            "color_ref_code": cid if cid else None,
            "sku": sku,
            "size_name": size_name,
            "size_ref_code": None,
            "price": price_unit,
            "launch_price": launch_price_unit,
            "availability": availability,
            "sole_material": None,
            "upper_material": None,
            "occasion": None,
            "closure_type": None,
            "toe_type": None,
            "heel_type": None,
            "weight": None,
            "heel_to_toe_drop": None,
            "origin": None,
            "images": images
        }

        all_products.append(entry)

    return all_products


def get_folders(path, exclude=None):
    if exclude is None:
        exclude = []
    if not os.path.exists(path):
        return []
    return [f for f in os.listdir(path) if f not in exclude and '.json' not in f]


def process_jsons(today_str: str, country: str, collection):
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = get_folders(gender_folder)
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder)
        for category in categories:
            file_folder = os.path.join(category_folder, category)
            if not os.path.exists(file_folder):
                continue
            for file_name in os.listdir(file_folder):
                file_path = os.path.join(file_folder, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    skus = create_individual_json(today_str, data)
                    if skus:
                        try:
                            collection.insert_many(skus)
                        except Exception:
                            for s in skus:
                                try:
                                    collection.insert_one(s)
                                except Exception as ie:
                                    print(f"Insert error for SKU {s.get('sku')}: {ie}")
                        for sku in skus:
                            print(f'Product_id: {sku["product_id"]}, SKU: {sku["sku"]}')
                    else:
                        print(f"Skipping {file_name} - not shoe or missing data")
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    traceback.print_exc()


if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-11-17'
    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client['tg_analytics']
    countries = ['India']
    for country in countries:
        collection = db[f'crawler_sink_comet_{country.lower()}_footwear']
        print(f"Processing {country} footwear...")
        data_path = os.path.join(country, 'Data')
        if not os.path.exists(data_path):
            continue
        for today_subfolder in os.listdir(data_path):
            process_jsons(today_subfolder, country, collection)
        print(f"Footwear data loading for {country} completed!")
    client.close()
