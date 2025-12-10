import os
import json
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from requests.exceptions import RequestException

# Directory paths
BASE_INPUT_DIR = os.path.join("South_korea", "Data", datetime.today().strftime("%Y-%m-%d"), "Item_urls")
BASE_OUTPUT_DIR = os.path.join("South_korea", "Data", datetime.today().strftime("%Y-%m-%d"), "Json_data")
PRODUCT_URLS_FILE = os.path.join(BASE_INPUT_DIR, "unique_product_urls.json")

# Create base output directory if it doesn't exist
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

def extract_handle_from_url(url):
    """Extract Shopify product handle from URL"""
    try:
        path = urlparse(url).path
        parts = path.strip("/").split("/")
        if "products" in parts:
            idx = parts.index("products")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    except Exception:
        return None
    return None

def fetch_product_data(handle, category):
    """Fetch product data from both .json and .js endpoints"""
    # Define output directory based on category
    category_output_dir = os.path.join(BASE_OUTPUT_DIR, category)
    os.makedirs(category_output_dir, exist_ok=True)  # Create category directory if it doesn't exist
    output_file = os.path.join(category_output_dir, f"{handle}.json")
    
    # Skip if file already exists
    if os.path.exists(output_file):
        print(f"Skipping existing file for handle: {handle} in category: {category}")
        return handle, None, category

    endpoints = {
        "json": f"https://lewkin.com/en-kr/products/{handle}.json",
        "js": f"https://lewkin.com/en-kr/products/{handle}.js"
    }

    combined_data = {}

    # Fetch .json endpoint
    try:
        resp = requests.get(endpoints["json"], timeout=5)
        if resp.ok:
            combined_data["json_data"] = resp.json()
        else:
            print(f"Failed JSON for {handle} (Status: {resp.status_code})")
    except RequestException as e:
        print(f"Error fetching JSON for {handle} - {e}")

    # Fetch .js endpoint
    try:
        resp = requests.get(endpoints["js"], timeout=5)
        if resp.ok:
            try:
                # Try parsing JS as JSON (Shopify usually returns valid JSON-compatible data)
                combined_data["js_data"] = resp.json()
            except Exception:
                # If parsing fails, save raw text
                combined_data["js_data"] = {"raw": resp.text}
        else:
            print(f"Failed JS for {handle} (Status: {resp.status_code})")
    except RequestException as e:
        print(f"Error fetching JS for {handle} - {e}")

    return handle, combined_data if combined_data else None, category

def main():
    # Load product URLs
    try:
        with open(PRODUCT_URLS_FILE, "r", encoding="utf-8") as f:
            product_urls_json = json.load(f)
    except FileNotFoundError:
        print(f"Error: {PRODUCT_URLS_FILE} not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {PRODUCT_URLS_FILE}.")
        return

    # Create a mapping of URLs to categories
    url_to_category = {}
    all_urls = set()
    for cat, urls in product_urls_json.items():
        if isinstance(urls, list):
            for url in urls:
                url_to_category[url] = cat
                all_urls.add(url)
        else:
            url_to_category[urls] = cat
            all_urls.add(urls)

    # Extract handles and associate with categories
    handle_to_category = {}
    handles = []
    for url in all_urls:
        handle = extract_handle_from_url(url)
        if handle:
            handles.append(handle)
            handle_to_category[handle] = url_to_category.get(url, "unknown")

    print(f"Found {len(handles)} product handles to process.")

    # Use ThreadPoolExecutor for concurrent requests
    max_workers = 6
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_handle = {
            executor.submit(fetch_product_data, handle, handle_to_category[handle]): handle
            for handle in handles
        }
        
        # Process completed tasks
        for future in as_completed(future_to_handle):
            handle = future_to_handle[future]
            try:
                handle, data, category = future.result()
                if data:
                    category_output_dir = os.path.join(BASE_OUTPUT_DIR, category)
                    output_file = os.path.join(category_output_dir, f"{handle}.json")
                    with open(output_file, "w", encoding="utf-8") as f_out:
                        json.dump(data, f_out, indent=2, ensure_ascii=False)
                    print(f"Saved data for handle: {handle} in category: {category}")
            except Exception as e:
                print(f"Error processing handle {handle}: {e}")

    print(f"Completed processing. Saved files in: {BASE_OUTPUT_DIR}")

if __name__ == "__main__":
    main()