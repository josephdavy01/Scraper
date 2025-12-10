# import os
# import json
# from datetime import datetime
# from playwright.sync_api import sync_playwright
# from bs4 import BeautifulSoup

# # ====== Directory Setup ======
# BASE_DIR = os.path.join("UAE","Data" ,datetime.today().strftime("%Y-%m-%d"))
# ITEM_URLS_DIR = os.path.join(BASE_DIR, "Item_urls")
# os.makedirs(ITEM_URLS_DIR, exist_ok=True)

# # MAX_SUBCATEGORY_URLS = 7 # limit per subcategory

# category_file = os.path.join(ITEM_URLS_DIR, "UAE_category_urls.json")
# url_json_path = os.path.join(ITEM_URLS_DIR, "UAE_product_urls.json")

# # Check if product URLs file already exists
# if os.path.exists(url_json_path) and os.path.getsize(url_json_path) > 0:
#     print(f"⏭️ Skipping product URL scraping: File {url_json_path} already exists and is non-empty")
#     with open(url_json_path, "r", encoding="utf-8") as f:
#         structured_data = json.load(f)
#     all_product_urls = []
#     def extract_urls(data):
#         if isinstance(data, list):
#             all_product_urls.extend(data)
#         elif isinstance(data, dict):
#             for value in data.values():
#                 extract_urls(value)
#     extract_urls(structured_data)
# else:
#     with open(category_file, "r", encoding="utf-8") as f:
#         categories = json.load(f)

#     # ====== Helpers ======
#     def click_load_more(page):
#         prev_count = -1
#         while True:
#             try:
#                 load_more = page.query_selector(
#                     'button:text("Load more Products"), a:text("Load more Products")'
#                 )
#                 if not load_more:
#                     break
#                 if not load_more.is_visible():
#                     break
#                 load_more.scroll_into_view_if_needed()
#                 load_more.click()
#                 page.wait_for_timeout(19000)
#             except Exception:
#                 break

#             soup = BeautifulSoup(page.content(), "html.parser")
#             count = len(soup.select("div.product-item-info-top"))
#             if count == prev_count:
#                 break
#             prev_count = count

#     def extract_product_urls(page):
#         soup = BeautifulSoup(page.content(), "html.parser")
#         products = []
#         for prod_div in soup.select("div.product-item-info-top"):
#             a_tag = prod_div.find("a", class_="product-item-title")
#             if not a_tag:
#                 continue
#             href = a_tag.get("href")
#             if href and href.startswith("/"):
#                 href = "https://www.newbalance.co.ae" + href
#             products.append(href)
#         return products

#     def scrape_product_details(page, product_url):
#         page.goto(product_url)
#         page.wait_for_timeout(200000)

#         soup = BeautifulSoup(page.content(), "html.parser")

#         product_data = {}
#         product_data["url"] = product_url
#         product_data["title"] = (
#             soup.select_one("h1.product-name").text.strip()
#             if soup.select_one("h1.product-name")
#             else ""
#         )
#         product_data["price"] = (
#             soup.select_one("span.price").text.strip()
#             if soup.select_one("span.price")
#             else ""
#         )
#         launch_price_elem = soup.select_one("span.dropin-price--strikethrough")
#         product_data["launch_price"] = (
#         launch_price_elem.text.strip() if launch_price_elem else ""
#     )
#         variants = []
#         size_elements = soup.select("select#size-select option")
#         for option in size_elements:
#             size = option.text.strip()
#             available = "disabled" not in option.attrs
#             variants.append({"size": size, "available": available})
#         product_data["variants"] = variants

#         return product_data

#     # ====== Main Scraping ======
#     all_product_urls = []
#     structured_data = {}

#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=False)
#         page = browser.new_page(viewport={"width": 1280, "height": 800})

#         # Scrape categories -> product URLs
#         for lvl2_name, lvl3_dict in list(categories.items()):
#         # [:MAX_SUBCATEGORY_URLS]:
#             print(f"Category: {lvl2_name}")
#             structured_data[lvl2_name] = {}

#             if isinstance(lvl3_dict, str):
#                 url = lvl3_dict
#                 print(f"  Loading category URL: {url}")
#                 page.goto(url)
#                 page.wait_for_timeout(16000)
#                 click_load_more(page)
#                 products = extract_product_urls(page)
#                 structured_data[lvl2_name] = products
#                 all_product_urls.extend(products)
#             elif isinstance(lvl3_dict, dict):
#                 for lvl3_name, lvl4_dict in list(lvl3_dict.items()):
#                 # [:MAX_SUBCATEGORY_URLS]:
#                     print(f"  Subcategory: {lvl3_name}")
#                     structured_data[lvl2_name][lvl3_name] = {}

#                     if isinstance(lvl4_dict, str):
#                         url = lvl4_dict
#                         print(f"    Loading URL: {url}")
#                         page.goto(url)
#                         page.wait_for_timeout(15000)
#                         click_load_more(page)
#                         products = extract_product_urls(page)
#                         structured_data[lvl2_name][lvl3_name] = products
#                         all_product_urls.extend(products)
#                     elif isinstance(lvl4_dict, dict):
#                         for lvl4_name, url in list(lvl4_dict.items()):
#                         # [:MAX_SUBCATEGORY_URLS]:
#                             print(f"    Sub-subcategory: {lvl4_name} - {url}")
#                             page.goto(url)
#                             page.wait_for_timeout(16000)
#                             click_load_more(page)
#                             products = extract_product_urls(page)
#                             structured_data[lvl2_name][lvl3_name][lvl4_name] = products
#                             all_product_urls.extend(products)

#         # Save category-product URLs JSON
#         with open(url_json_path, "w", encoding="utf-8") as f:
#             json.dump(structured_data, f, indent=2)

#         print(f"Product URLs saved. Total URLs: {len(all_product_urls)}")

#         browser.close()

# # Check if product details file already exists
import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# ====== Directory Setup ======
BASE_DIR = os.path.join("UAE", "Data", datetime.today().strftime("%Y-%m-%d"))
ITEM_URLS_DIR = os.path.join(BASE_DIR, "Item_urls")
os.makedirs(ITEM_URLS_DIR, exist_ok=True)

category_file = os.path.join(ITEM_URLS_DIR, "UAE_category_urls.json")
url_json_path = os.path.join(ITEM_URLS_DIR, "UAE_product_urls.json")

# ------------------------------------------------------------------
# 1. Skip if we already have the product-URL file
# ------------------------------------------------------------------
if os.path.exists(url_json_path) and os.path.getsize(url_json_path) > 0:
    print(f"Skipping product URL scraping: File {url_json_path} already exists and is non-empty")
    with open(url_json_path, "r", encoding="utf-8") as f:
        structured_data = json.load(f)
    all_product_urls = []
    def flatten(data):
        if isinstance(data, list):
            all_product_urls.extend(data)
        elif isinstance(data, dict):
            for v in data.values():
                flatten(v)
    flatten(structured_data)
else:
    # ------------------------------------------------------------------
    # 2. Load category tree
    # ------------------------------------------------------------------
    with open(category_file, "r", encoding="utf-8") as f:
        categories = json.load(f)

    # ------------------------------------------------------------------
    # 3. Helpers
    # ------------------------------------------------------------------
    def click_load_more(page):
        prev_count = -1
        while True:
            try:
                load_more = page.query_selector(
                    'button:text("Load more Products"), a:text("Load more Products")'
                )
                if not load_more or not load_more.is_visible():
                    break
                load_more.scroll_into_view_if_needed()
                load_more.click()
                page.wait_for_timeout(19000)
            except Exception:
                break

            soup = BeautifulSoup(page.content(), "html.parser")
            count = len(soup.select("div.product-item-info-top"))
            if count == prev_count:
                break
            prev_count = count

    def extract_product_urls(page):
        soup = BeautifulSoup(page.content(), "html.parser")
        products = []
        for prod_div in soup.select("div.product-item-info-top"):
            a_tag = prod_div.find("a", class_="product-item-title")
            if not a_tag:
                continue
            href = a_tag.get("href")
            if href and href.startswith("/"):
                href = "https://www.newbalance.co.ae" + href
            products.append(href)
        return products

    # NEW: print count for the current URL + store it
    def print_category_count(url, products, path_parts):
        count = len(products)
        path_str = " > ".join(path_parts) if path_parts else "ROOT"
        print(f"    Loaded: {url:<60} → {count:>4} products  ({path_str})")
        return count

    # ------------------------------------------------------------------
    # 4. Main scraping
    # ------------------------------------------------------------------
    all_product_urls = []
    structured_data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        for lvl2_name, lvl3_dict in categories.items():
            print(f"Category: {lvl2_name}")
            structured_data[lvl2_name] = {}

            if isinstance(lvl3_dict, str):
                # Level-2 is a direct URL
                url = lvl3_dict
                print(f"  Loading category URL: {url}")
                page.goto(url)
                page.wait_for_timeout(16000)
                click_load_more(page)
                products = extract_product_urls(page)
                structured_data[lvl2_name] = products
                all_product_urls.extend(products)
                print_category_count(url, products, [lvl2_name])

            elif isinstance(lvl3_dict, dict):
                for lvl3_name, lvl4_dict in lvl3_dict.items():
                    print(f"  Subcategory: {lvl3_name}")
                    structured_data[lvl2_name][lvl3_name] = {}

                    if isinstance(lvl4_dict, str):
                        # Level-3 is a direct URL
                        url = lvl4_dict
                        print(f"    Loading URL: {url}")
                        page.goto(url)
                        page.wait_for_timeout(15000)
                        click_load_more(page)
                        products = extract_product_urls(page)
                        structured_data[lvl2_name][lvl3_name] = products
                        all_product_urls.extend(products)
                        print_category_count(url, products, [lvl2_name, lvl3_name])

                    elif isinstance(lvl4_dict, dict):
                        for lvl4_name, url in lvl4_dict.items():
                            print(f"    Sub-subcategory: {lvl4_name} - {url}")
                            page.goto(url)
                            page.wait_for_timeout(16000)
                            click_load_more(page)
                            products = extract_product_urls(page)
                            structured_data[lvl2_name][lvl3_name][lvl4_name] = products
                            all_product_urls.extend(products)
                            print_category_count(url, products, [lvl2_name, lvl3_name, lvl4_name])

        # ------------------------------------------------------------------
        # 5. Save product-URL JSON
        # ------------------------------------------------------------------
        with open(url_json_path, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, indent=2, ensure_ascii=False)

        print(f"\nProduct URLs saved. Total URLs: {len(all_product_urls)}")
        browser.close()

# ------------------------------------------------------------------
# 6. FINAL SUMMARY (same as before – now works whether we scraped or skipped)
# ------------------------------------------------------------------
with open(url_json_path, "r", encoding="utf-8") as f:
    structured_data = json.load(f)

def count_urls(node, path, counts):
    if isinstance(node, list):
        counts[" > ".join(path)] = len(node)
    elif isinstance(node, dict):
        for k, v in node.items():
            count_urls(v, path + [k], counts)

url_counts = {}
count_urls(structured_data, [], url_counts)

# print("\n" + "="*70)
# print("PRODUCT URL COUNTS PER CATEGORY (FINAL SUMMARY)")
# print("="*70)
total = 0
# for cat_path, cnt in sorted(url_counts.items()):
#     print(f"{cat_path:<55} → {cnt:>5} URLs")
#     total += cnt
# print("-"*70)
print(f"{'TOTAL':<55} → {total:>5} URLs")
print("="*70 + "\n")

counts_path = os.path.join(ITEM_URLS_DIR, "UAE_product_urls_counts.json")
with open(counts_path, "w", encoding="utf-8") as f:
    json.dump(url_counts, f, indent=2, ensure_ascii=False)
print(f"Counts saved to: {counts_path}")