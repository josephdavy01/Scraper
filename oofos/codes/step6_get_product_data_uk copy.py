#!/usr/bin/env python3
from datetime import date
import json
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse, unquote

# ---------- CONFIG ----------
BASE_URL = "https://www.oofos.co.uk"
TIMEOUT = 15
RETRY_COUNT = 2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------- SAVE & CHECK ---------------- #

def save_json(name, json_data, date_subfolder, category, subcategory):
    try:
        json_path = date_subfolder / 'Json_data' / category / subcategory
        json_path.mkdir(parents=True, exist_ok=True)
        with open(json_path / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        logging.info(f"Saved JSON → Json_data/{category}/{subcategory}/{name}.json")
    except Exception as e:
        logging.error(f"Error saving JSON for {name}: {e}")

def check_file(name, date_subfolder, category, subcategory):
    return (date_subfolder / "Json_data" / category / subcategory / f"{name}.json").exists()

# ---------------- HANDLE PARSING ---------------- #

def is_collection_url(parsed):
    path = parsed.path.lower()
    if '/products/' in path:
        return False
    if '/collections/' in path or '/collection/' in path or '/category/' in path:
        return True
    if any(seg in path for seg in ['/sale', '/clearance', '/featured', '/new', '/outlet']):
        return True
    last = parsed.path.rstrip("/").split("/")[-1]
    if "-" in last and len(last) > 3:
        return False
    return True

def extract_handle_from_url(url):
    try:
        parsed = urlparse(url)
        path = parsed.path
        if "/products/" in path:
            after = path.split("/products/", 1)[1].rstrip("/")
            handle = after.split("/")[0]
            handle = unquote(handle).split(".")[0]
            return handle or None
        if is_collection_url(parsed):
            return None
        last = path.rstrip("/").split("/")[-1]
        last = unquote(last).split(".")[0]
        return last or None
    except Exception:
        return None

# ---------------- CATEGORY EXTRACTION (FIXED) ---------------- #

def extract_urls_by_category(data):
    """
    Fixed extractor:
    Returns:
      {
        "men": { "mens-clogs": [...], ... },
        "women": { ... },
        "sale": { "all": [...], ... },
        ...
      }
    """
    categories = {}

    def add(cat, subcat, url):
        if not isinstance(url, str):
            return
        categories.setdefault(cat, {})
        categories[cat].setdefault(subcat, [])
        categories[cat][subcat].append(url)

    if not isinstance(data, dict):
        logging.warning(f"Input JSON is type {type(data).__name__}; expected dict at top-level.")
        return categories

    # Handle explicit gender keys first
    for gender in ["men", "women"]:
        if gender in data:
            val = data[gender]
            if isinstance(val, dict):
                for subcat, urls in val.items():
                    if isinstance(urls, list):
                        for u in urls:
                            add(gender, subcat, u)
            elif isinstance(val, list):
                for u in val:
                    add(gender, "all", u)

    # Handle other top-level keys (sale, new, clearance, etc.)
    for key, val in data.items():
        lk = key.lower()
        if lk in ["men", "women"]:
            continue

        if isinstance(val, list):
            for u in val:
                add(lk, "all", u)

        elif isinstance(val, dict):
            # FIXED: iterate the list items (don't pass the list itself to add)
            for subcat, urls in val.items():
                if isinstance(urls, list):
                    for u in urls:
                        add(lk, subcat, u)
                else:
                    # if nested value isn't list, try to coerce string values
                    if isinstance(urls, str):
                        add(lk, subcat, urls)

    # Deduplicate URLs
    cleaned = {}
    for cat, subs in categories.items():
        clean_subs = {}
        for subcat, urls in subs.items():
            clean_urls = list(dict.fromkeys([u for u in urls if isinstance(u, str)]))
            if clean_urls:
                clean_subs[subcat] = clean_urls
        if clean_subs:
            cleaned[cat] = clean_subs

    return cleaned

# ---------------- PRODUCT JSON FETCH ---------------- #

def fetch_full_product_json(url_map, date_subfolder, base_url=BASE_URL):
    skipped = []
    total = 0

    for category, subcats in url_map.items():
        for subcat, urls in subcats.items():
            for url in urls:
                total += 1
                handle = extract_handle_from_url(url)
                if not handle:
                    logging.warning(f"SKIP (collection or invalid): {url} → {category}/{subcat}")
                    skipped.append({'url': url, 'category': category, 'subcategory': subcat})
                    continue

                if check_file(handle, date_subfolder, category, subcat):
                    logging.info(f"Already exists → {category}/{subcat}/{handle}")
                    continue

                json_url = f"{base_url.rstrip('/')}/products/{handle}.json"
                last_error = None
                for attempt in range(1, RETRY_COUNT + 1):
                    try:
                        logging.info(f"Fetching {json_url} → {category}/{subcat} (Attempt {attempt})")
                        r = requests.get(json_url, timeout=TIMEOUT)

                        if r.status_code == 200:
                            try:
                                data = r.json()
                            except Exception:
                                data = json.loads(r.text)
                            save_json(handle, data, date_subfolder, category, subcat)
                            break
                        else:
                            logging.warning(f"[{r.status_code}] {json_url}")
                            last_error = Exception(r.status_code)
                    except Exception as e:
                        last_error = e
                        logging.error(f"Error fetching {json_url}: {e}")
                else:
                    logging.error(f"Failed after retries: {json_url} ({last_error})")

    logging.info(f"\nTotal processed: {total}")
    logging.info(f"Skipped: {len(skipped)}")

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    country = "UK"
    today = date.today().strftime("%Y-%m-%d")
    date_subfolder = Path(country) / "Data" / today
    input_file = date_subfolder / "Item_urls" / f"unique_product_urls copy.json"

    if not input_file.exists():
        raise FileNotFoundError(f"Missing input file: {input_file}")

    raw_text = input_file.read_text(encoding="utf-8")
    try:
        raw_data = json.loads(raw_text)
    except Exception as e:
        logging.error(f"Failed to parse JSON input: {e}")
        raise

    # Quick diagnostics (helps spot structure issues)
    if isinstance(raw_data, dict):
        logging.info(f"Top-level keys: {list(raw_data.keys())[:20]}")
    else:
        logging.info(f"Top-level JSON type: {type(raw_data).__name__}")

    url_map = extract_urls_by_category(raw_data)

    # show what we detected
    if not url_map:
        logging.warning("No categories/subcategories found after extraction. Check input structure.")
    else:
        logging.info("\nDetected categories/subcategories:")
        for cat, subs in url_map.items():
            for subcat, urls in subs.items():
                logging.info(f"  {cat}/{subcat}: {len(urls)} URLs")

    fetch_full_product_json(url_map, date_subfolder)
    logging.info("\n Completed fetching all product JSONs.")
