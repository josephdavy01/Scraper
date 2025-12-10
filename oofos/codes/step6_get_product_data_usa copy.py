#!/usr/bin/env python3
from datetime import date
import json
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse, unquote

# ---------- CONFIG ----------
BASE_URL = "https://www.oofos.com"
TIMEOUT = 15
RETRY_COUNT = 2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def save_json(name, json_data, date_subfolder, category, subcategory):
    """
    Save JSON file under:
      date_subfolder / 'Json_data' / category / subcategory / {name}.json
    """
    try:
        json_path = date_subfolder / 'Json_data' / category / subcategory
        json_path.mkdir(parents=True, exist_ok=True)
        with open(json_path / f'{name}.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        logging.info(f"Saved JSON for {name} in Json_data/{category}/{subcategory}")
    except Exception as e:
        logging.error(f"Error saving JSON for {name} in {category}/{subcategory}: {e}")

def check_file(name, date_subfolder, category, subcategory):
    return (date_subfolder / 'Json_data' / category / subcategory / f'{name}.json').exists()

def is_collection_url(parsed):
    """
    Treat any path that contains '/products/' as a product,
    even if it also contains '/collections/'.
    Otherwise, try to detect collection-like paths.
    """
    path = parsed.path.lower()
    if '/products/' in path:
        return False
    if '/collections/' in path or '/collection/' in path or '/c/' in path or '/category/' in path or '/browse/' in path:
        return True
    if any(seg in path for seg in ['/sale', '/clearance', '/featured', '/new', '/outlet']):
        return True
    last = parsed.path.rstrip('/').split('/')[-1]
    if '-' in last and len(last) > 3:
        return False
    return True

def extract_handle_from_url(url):
    """
    Robustly extract product handle:
      - If '/products/' in path, take the first segment after '/products/'.
      - Else, if the last path segment looks like a slug and the path is not a collection, use it.
    Returns None if it's likely a collection or invalid.
    """
    try:
        parsed = urlparse(url)
        path = parsed.path
        if '/products/' in path:
            after = path.split('/products/', 1)[1].rstrip('/')
            handle = after.split('/')[0] if after else ''
            handle = unquote(handle)
            handle = handle.split('.')[0]
            return handle or None

        if is_collection_url(parsed):
            return None

        last = path.rstrip('/').split('/')[-1]
        last = unquote(last)
        if not last or last in ['collections', 'products', '']:
            return None
        last = last.split('.')[0]
        return last or None
    except Exception:
        return None

def extract_urls_by_category(data):
    """
    Returns mapping:
      {
        "men": { "mens-clogs": [urls...], "all": [urls...] , ... },
        "women": { "womens-sandals": [...], ... },
        "sale": { "all": [...], "clearance-subcat": [...] },
        "new": { "all": [...] },
        ...
      }
    Rules:
      - If input has explicit 'men' or 'women' dicts, keep their nested category names.
      - If input has 'men' or 'women' lists, put them under men/all or women/all.
      - If other top-level keys exist (sale, new, clearance), if they are lists -> category/all.
        If they are dicts -> flatten one level into category_subcat.
    """
    categories = {}

    def add(cat, subcat, url):
        if not isinstance(url, str):
            return
        categories.setdefault(cat, {})
        categories[cat].setdefault(subcat, [])
        categories[cat][subcat].append(url)

    if not isinstance(data, dict):
        return {}

    # Handle explicit genders first
    for gender in ['men', 'women']:
        if gender in data:
            val = data[gender]
            if isinstance(val, dict):
                for subcat, urls in val.items():
                    if isinstance(urls, list):
                        for u in urls:
                            add(gender, subcat, u)
            elif isinstance(val, list):
                for u in val:
                    add(gender, 'all', u)

    # Handle other top-level keys (sale, new, clearance, etc.)
    for key, val in data.items():
        lk = key.lower()
        if lk in ['men', 'women']:
            continue
        if isinstance(val, list):
            for u in val:
                add(lk, 'all', u)
        elif isinstance(val, dict):
            # Flatten one level: key_subkey becomes subcategory under key
            for subk, subv in val.items():
                if isinstance(subv, list):
                    for u in subv:
                        # prefer using the subcategory name directly under key
                        add(lk, subk, u)

    # Deduplicate URLs
    cleaned = {}
    for cat, subs in categories.items():
        clean_subs = {}
        for sub, urls in subs.items():
            unique = list(dict.fromkeys([u for u in urls if isinstance(u, str)]))
            if unique:
                clean_subs[sub] = unique
        if clean_subs:
            cleaned[cat] = clean_subs
    return cleaned

def fetch_full_product_json(urls_map, date_subfolder, base_url=BASE_URL):
    """
    urls_map: { category: { subcategory: [urls...] } }
    Saves each product JSON to:
      date_subfolder / 'Json_data' / category / subcategory / {handle}.json
    """
    skipped = []
    total_tried = 0
    for category, subcats in urls_map.items():
        for subcat, urls in subcats.items():
            for url in urls:
                total_tried += 1
                handle = extract_handle_from_url(url)
                if not handle:
                    logging.warning(f"SKIP (likely collection or cannot parse handle): {url} (category={category}/{subcat})")
                    skipped.append({'url': url, 'category': category, 'subcategory': subcat})
                    continue

                if check_file(handle, date_subfolder, category, subcat):
                    logging.info(f"Skipping (already exists): {handle} in Json_data/{category}/{subcat}")
                    continue

                json_url = f"{base_url.rstrip('/')}/products/{handle}.json"
                last_exception = None
                for attempt in range(1, RETRY_COUNT + 1):
                    try:
                        logging.info(f"Fetching ({attempt}/{RETRY_COUNT}) {json_url} -> Json_data/{category}/{subcat}")
                        response = requests.get(json_url, timeout=TIMEOUT)
                        if response.status_code == 200:
                            try:
                                data = response.json()
                            except ValueError:
                                data = json.loads(response.text)
                            save_json(handle, data, date_subfolder, category, subcat)
                            break
                        else:
                            body = response.text[:800]
                            logging.warning(f"Non-200 for {json_url}: {response.status_code}. Body (truncated): {body!r}")
                            last_exception = Exception(f"status {response.status_code}")
                    except Exception as e:
                        logging.error(f"Error fetching {json_url} (attempt {attempt}): {e}")
                        last_exception = e
                else:
                    logging.error(f"Failed after {RETRY_COUNT} attempts: {json_url}. Last error: {last_exception}")

    if skipped:
        logging.info(f"\nSkipped {len(skipped)} URLs (likely collections or ambiguous). Example 10:")
        for s in skipped[:10]:
            logging.info(f"  - {s['url']}  (category={s['category']}/{s['subcategory']})")
    logging.info(f"\nTried to process {total_tried} input URLs (products attempted where handle parsed).")

# -------------------- main --------------------
if __name__ == "__main__":
    country = "USA"   
    today = date.today().strftime('%Y-%m-%d')
    date_subfolder = Path(country) / "Data" / today
    input_file_path = date_subfolder / "Item_urls" / f"{country}_unique_product_urls.json"

    if not input_file_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file_path}")

    with open(input_file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    urls_map = extract_urls_by_category(raw_data)

    # Count total URLs
    total_urls = sum(len(urls) for subs in urls_map.values() for urls in subs.values())
    if total_urls == 0:
        logging.error("No URLs found in the input file after extraction.")
        logging.info(f"Top-level keys in input: {list(raw_data.keys()) if isinstance(raw_data, dict) else 'not a dict'}")
        if isinstance(raw_data, dict):
            for k in list(raw_data.keys())[:10]:
                logging.info(f"  - {k}: type={type(raw_data[k])}")
        raise ValueError("No URLs found in the input file.")

    logging.info("\n✓ Found URLs (by category/subcategory):")
    for cat, subs in urls_map.items():
        for sub, urls in subs.items():
            logging.info(f"  - {cat}/{sub}: {len(urls)} products")

    fetch_full_product_json(urls_map, date_subfolder)

    logging.info(f"\n✓ Completed fetching JSONs for {total_urls} products.")
