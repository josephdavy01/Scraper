# import os
# import json
# import re
# from datetime import datetime
# from playwright.sync_api import sync_playwright

# # Define base URL and save directory with date folder
# BASE_URL = "https://lewkin.com/en-kr"
# SAVE_DIR = os.path.join("South_korea", "Data", datetime.today().strftime("%Y-%m-%d"), "Item_urls")
# os.makedirs(SAVE_DIR, exist_ok=True)

# # Set paths for input categories JSON and output IDs JSON
# categories_file = os.path.join(SAVE_DIR, "categories_urls.json")     # input file path
# output_file = os.path.join(SAVE_DIR, "categories_ids.json")          # output file path

# def load_categories(json_file):
#     with open(json_file, "r", encoding="utf-8") as f:
#         return json.load(f)

# def extract_rid_from_page(page_html):
#     match = re.search(r'"rid":\s*(\d+)', page_html)
#     return match.group(1) if match else None

# def get_cat_ids(categories_json):
#     cat_id_map = {}
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=False)
#         page = browser.new_page()
#         # categories_json is nested dictionary
#         for main_cat, subcats in categories_json.items():
#             if isinstance(subcats, dict):
#                 for cat_name, url in subcats.items():
#                     page.goto(url,wait_until="domcontentloaded")
#                     html = page.content()
#                     rid = extract_rid_from_page(html)
#                     cat_id_map[cat_name] = rid
#             else:
#                 # in case subcats is a single URL string
#                 url = subcats
#                 page.goto(url)
#                 html = page.content()
#                 rid = extract_rid_from_page(html)
#                 cat_id_map[main_cat] = rid
#         browser.close()
#     return cat_id_map

# def save_cat_ids(cat_id_map, output_file):
#     with open(output_file, "w", encoding="utf-8") as f:
#         json.dump(cat_id_map, f, indent=2, ensure_ascii=False)

# if __name__ == "__main__":
#     categories_json = load_categories(categories_file)
#     cat_id_map = get_cat_ids(categories_json)
#     save_cat_ids(cat_id_map, output_file)
    
#     print(f"Saved category IDs to {output_file}")

import os
import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# Define base URL and save directory with date folder
BASE_URL = "https://lewkin.com/en-kr"
SAVE_DIR = os.path.join("South_korea", "Data", datetime.today().strftime("%Y-%m-%d"), "Item_urls")
os.makedirs(SAVE_DIR, exist_ok=True)

# Input + Output file paths
categories_file = os.path.join(SAVE_DIR, "categories_urls.json")
output_file = os.path.join(SAVE_DIR, "categories_ids.json")

def load_categories(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)

def load_saved_ids(output_file):
    """Load saved IDs if file exists, otherwise return empty dict."""
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_single_id(cat_name, rid, output_file):
    """Save one category ID immediately."""
    saved = load_saved_ids(output_file)
    saved[cat_name] = rid
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=2, ensure_ascii=False)

def extract_rid_from_page(html):
    match = re.search(r'"rid":\s*(\d+)', html)
    return match.group(1) if match else None

def close_popups(page):
    popup_selectors = [
        "button[aria-label='Close']",
        "button.close",
        ".close-button",
        ".popup-close",
        ".modal-close",
        "button[data-testid='close-button']",
        "button[aria-label='닫기']"
    ]

    for selector in popup_selectors:
        try:
            if page.locator(selector).is_visible():
                page.locator(selector).click()
                page.wait_for_timeout(500)
        except:
            pass

def get_cat_ids(categories_json):
    saved_ids = load_saved_ids(output_file)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        for main_cat, subcats in categories_json.items():

            # Handle dictionary and single URL case
            if isinstance(subcats, dict):
                iterable = subcats.items()
            else:
                iterable = [(main_cat, subcats)]

            for cat_name, url in iterable:

                # Skip if already scraped
                if cat_name in saved_ids:
                    print(f"[SKIP] {cat_name} already saved.")
                    continue

                print(f"[SCRAPING] Category: {cat_name} | URL: {url}")

                page.goto(url, wait_until="domcontentloaded")

                # Wait for scripts to load
                page.wait_for_timeout(5000)

                # Close potential pop-ups
                close_popups(page)

                html = page.content()
                rid = extract_rid_from_page(html)

                print(f" → Extracted RID: {rid}")

                # Save immediately
                save_single_id(cat_name, rid, output_file)

                print(f" → Saved '{cat_name}': {rid}\n")

        browser.close()

    print("Scraping completed.")

if __name__ == "__main__":
    categories_json = load_categories(categories_file)
    get_cat_ids(categories_json)
