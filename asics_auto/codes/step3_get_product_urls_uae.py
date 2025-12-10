import os
import json
import time
import random
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from playwright.sync_api import sync_playwright

country = "UAE"

def add_pagination_params(url, page_number, limit=36):
    parsed = urlparse(url)
    query_parts = []
    if page_number > 1:
        query_parts.append(f"p={page_number}")
    query_parts.append(f"product_list_limit={limit}")
    new_query = "&".join(query_parts)
    return urlunparse(parsed._replace(query=new_query))

def human_delay(min_sec=5, max_sec=12):
    s = random.uniform(min_sec, max_sec)
    print(f"Sleeping for {s:.2f}s before next request...")
    time.sleep(s)

def extract_products(page, product_urls):
    selector = "div.product-item-info.not-new a.product.photo.product-item-photo._has-additional"
    elements = page.locator(selector)
    count = elements.count()
    if count > 0:
        print(f"Found {count} products")
        for i in range(count):
            href = elements.nth(i).get_attribute("href")
            if href and href not in product_urls:
                product_urls.append(href)
        return True
    return False

def scrape_product_urls(categories):
    product_data = {}
    for main_cat, subcats in categories.items():
        product_data[main_cat] = {}
        for subcat, base_url in subcats.items():
            print(f"\nScraping {main_cat} -> {subcat}")
            product_urls = []
            page_number = 1
            while True:
                next_url = add_pagination_params(base_url, page_number, limit=36)
                print(f"Visiting page {page_number}: {next_url}")
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False, slow_mo=50)
                    page = browser.new_page()
                    try:
                        page.goto(next_url, timeout=120000)
                        page.wait_for_selector(
                            "div.product-item-info.not-new a.product.photo.product-item-photo._has-additional",
                            timeout=60000
                        )
                    except:
                        print("Page did not load or selector not found.")
                        browser.close()
                        break
                    if not extract_products(page, product_urls):
                        print("No products found on this page. Stopping.")
                        browser.close()
                        break
                    print(f"Total collected so far: {len(product_urls)}")
                    next_button = page.locator("li.item.pages-item-next a")
                    has_next = next_button.count() > 0
                    browser.close() 
                if not has_next:
                    print("No more pages.")
                    break
                page_number += 1
                human_delay(1,3) 
            product_data[main_cat][subcat] = product_urls
    return product_data

if __name__ == "__main__":
    today_str = datetime.today().strftime("%Y-%m-%d")
    base_path = f"{country}/Data/{today_str}/Item_urls"
    os.makedirs(base_path, exist_ok=True)
    out_file = f"{base_path}/{country}_product_urls.json"
    read_file = f"{base_path}/{country}_category_urls.json"
    with open(read_file, "r", encoding="utf-8") as f:
        categories = json.load(f)
    data = scrape_product_urls(categories)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"\nSaved product URLs to {out_file}")
