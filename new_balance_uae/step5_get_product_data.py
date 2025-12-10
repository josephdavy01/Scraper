import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

# ========== DIRECTORIES ==========
BASE_DIR = os.path.join("UAE", 'Data', datetime.today().strftime("%Y-%m-%d"))
ITEM_URLS_DIR = os.path.join(BASE_DIR, "Item_urls")
JSON_DATA_DIR = os.path.join(BASE_DIR, "Json_data")
os.makedirs(JSON_DATA_DIR, exist_ok=True)
os.makedirs(ITEM_URLS_DIR, exist_ok=True)

# ========== LOAD PRODUCT URLS ==========
url_json_path = os.path.join(ITEM_URLS_DIR, "UAE_unique_product_urls.json")
try:
    with open(url_json_path, "r", encoding="utf-8") as f:
        structured_data = json.load(f)
except FileNotFoundError:
    print(f"Error: {url_json_path} not found. Please ensure the file exists.")
    exit(1)

# ---------- flatten + keep category hierarchy ----------
all_product_urls = []

def extract_urls(data, category="", subcategory="", subsubcategory=""):
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):  # leaf → list of URLs
                for url in value:
                    if isinstance(url, str) and url.strip():
                        all_product_urls.append({
                            "url": url,
                            "category": category or key,
                            "subcategory": subcategory or key,
                            "subsubcategory": subsubcategory
                        })
            else:  # deeper level
                if not category:
                    extract_urls(value, category=key)
                elif not subcategory:
                    extract_urls(value, category=category, subcategory=key)
                elif not subsubcategory:
                    extract_urls(value, category=category, subcategory=subcategory, subsubcategory=key)
                else:
                    extract_urls(value, category=category, subcategory=subcategory, subsubcategory=key)

extract_urls(structured_data)

print(f"\nTotal unique product URLs to scrape: {len(all_product_urls)}\n")
if not all_product_urls:
    print("No product URLs found in unique_product_urls.json")
    exit(1)

# ========== GALLERY IMAGES ==========
def extract_gallery_images(soup):
    images = []
    container = soup.find('div', {'class': 'pdp-gallery-grid pdp-product__images'})
    if container:
        for div in container.find_all('div', {'class': 'pdp-gallery-grid__item'}):
            img = div.find('img')
            if img and img.get('src'):
                src = img.get('src').split('?')[0]
                if src.startswith('/'):
                    src = "https://www.newbalance.co.ae" + src
                if src not in images:
                    images.append(src)
    return images

# ========== SCRAPE ONE PRODUCT ==========
def scrape_product_details(page, product_url, category, subcategory):
    try:
        page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        page.wait_for_selector('div.pdp-swatches__options', timeout=20000)
    except TimeoutError:
        print(f"Timeout loading {product_url}")
        return None

    soup = BeautifulSoup(page.content(), "html.parser")

    pdp_collection = soup.select_one('h4.pdp-collection')
    extracted_subcategory = pdp_collection.text.strip() if pdp_collection else subcategory or "Uncategorized"

    product_data = {
        "Product Id": "", "Product Name": "", "Date of Scraping": datetime.today().strftime("%Y-%m-%d"),
        "Product Url": product_url, "Category": category, "Subcategory": extracted_subcategory,
        "Description": "", "Product Reference Code": "", "SKU": "", "Color Name": "", "Color ID": "",
        "Sizes": {"EU": [], "UK": [], "US": []}, "Price": "", "Launch Price": "", "Availability": False,
        "Demand": "", "Images": [], "Variants": []
    }

    # JSON-LD (main product)
    json_ld = soup.select_one('script[type="application/ld+json"][data-name="product"]')
    if json_ld:
        try:
            data = json.loads(json_ld.string)
            product_data["Product Name"] = data.get("name", "")
            product_data["SKU"] = data.get("sku", "")
            product_data["Description"] = data.get("description", "")
            product_data["Images"] = data.get("image", [])

            offers = data.get("offers", {})
            if isinstance(offers, list) and offers:
                o = offers[0]
                product_data["Price"] = f"AED {o.get('price', '')}" if o.get("price") else ""
                product_data["Availability"] = o.get("availability") == "http://schema.org/InStock"
            elif isinstance(offers, dict):
                product_data["Price"] = f"AED {offers.get('price', '')}" if offers.get("price") else ""
                product_data["Availability"] = offers.get("availability") == "http://schema.org/InStock"
        except json.JSONDecodeError:
            pass

    if not product_data["Product Name"]:
        product_data["Product Name"] = soup.select_one('h1.pdp-product__title').text.strip() if soup.select_one('h1.pdp-product__title') else ""
    if not product_data["Description"]:
        product_data["Description"] = soup.select_one('div.pdp-product__description--content').text.strip() if soup.select_one('div.pdp-product__description--content') else ""

    # ---- Product Id / Reference Code (target Article No) ----
    ref = soup.select_one('ul.pdp-product-description__attribute--sku span')
    product_data["Product Reference Code"] = ref.text.strip() if ref else ""
    if product_data["Product Reference Code"]:
        product_data["Product Id"] = product_data["Product Reference Code"]
    elif product_data["SKU"]:
        product_data["Product Id"] = product_data["SKU"].split('-')[0] if '-' in product_data["SKU"] else product_data["SKU"]

    # ---- Default Color ----
    color_label = soup.select_one('div.pdp-swatches__field__label')
    if color_label and 'Color:' in color_label.text:
        product_data["Color Name"] = color_label.text.split('Color: ')[1].strip()
    else:
        try:
            opt = page.locator('select[aria-label="Color"]').locator('option[selected]').first
            product_data["Color Name"] = opt.text_content().strip()
        except:
            pass

    default_input = soup.select_one('div.pdp-swatches__options input[type="radio"][name="color"].dropin-text-swatch--selected')
    product_data["Color ID"] = default_input.get('id', '') if default_input else ""

    # ---- Sizes (default) ----
    html_avail = False
    for sz_type, sel in [("EU", 'div.size-eu.size_shoe_eu.eu_size.sizes-list'),
                         ("UK", 'div.size-uk.size_shoe_uk.uk_size.sizes-list'),
                         ("US", 'div.size-us.size_shoe_us.us_size.sizes-list')]:
        elem = soup.select_one(sel)
        if elem:
            for lbl in elem.select('label.dropin-text-swatch__label'):
                name = lbl.text.strip()
                ref = lbl.get('id', '')
                avail = 'dropin-text-swatch__label--out-of-stock' not in lbl.get('class', [])
                if avail:
                    html_avail = True
                product_data["Sizes"][sz_type].append({"name": name, "reference_code": ref, "available": avail})
    product_data["Availability"] = product_data["Availability"] or html_avail

    # ---- Price fallback ----
    if not product_data["Price"]:
        price = soup.select_one('div.pdp-price__current span')
        product_data["Price"] = price.text.strip() if price else ""
    launch = soup.select_one('span.dropin-price--strikethrough') or soup.select_one('div.pdp-price__old span')
    product_data["Launch Price"] = launch.text.strip() if launch else product_data["Price"]
    product_data["Demand"] = "High" if product_data["Price"] != product_data["Launch Price"] else ""

    # ---- Images fallback ----
    if not product_data["Images"]:
        product_data["Images"] = extract_gallery_images(soup)

    return product_data

# ========== MAIN LOOP WITH PROGRESS COUNT ==========
total_products = len(all_product_urls)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    for idx, info in enumerate(all_product_urls, start=1):
        url = info["url"]
        cat = info["category"] or "Uncategorized"
        sub = info["subcategory"] or "Uncategorized"

        # Progress counter
        print(f"Processing {idx}/{total_products}: {url}")

        product_data = scrape_product_details(page, url, cat, sub)
        if not product_data:
            print(f"Skipping {url} (load error)")
            continue

        prod_id = product_data.get("Product Id") or f"product_{idx}"
        final_sub = product_data["Subcategory"]
        folder = os.path.join(JSON_DATA_DIR, cat, final_sub)
        os.makedirs(folder, exist_ok=True)
        file_path = os.path.join(folder, f"{prod_id}.json")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(product_data, f, indent=2, ensure_ascii=False)

        # Print JSON path
        print(f"Saved JSON: {file_path}\n")

    browser.close()

print("\nFinished! All reachable products have a JSON file under Json_data/")
