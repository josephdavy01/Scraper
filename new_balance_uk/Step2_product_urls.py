import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup
from Proxy import ProxyManager

# Hardcoded proxy for the first attempt
hardcoded_proxy = {
    "server": "p.webshare.io:80",  # Replace with your proxy server (IP:port)
    "username": "xbdrkxqc",   # Replace with your proxy username
    "password": "qer2lfrtujb8"    # Replace with your proxy password
}
# Initialize ProxyManager
proxy_manager = ProxyManager(hardcoded_proxy, proxy_file="Webshare_100_proxies.txt")

BASE_DIR = os.path.join("UK", "data", datetime.today().strftime("%Y-%m-%d"))
ITEM_URLS_DIR = os.path.join(BASE_DIR, "item_urls")
os.makedirs(ITEM_URLS_DIR, exist_ok=True)

url = "https://www.newbalance.co.uk/"
# MAX_SUBCATEGORY_URLS = 3
PRODUCT_SELECTOR = "div.pdp-link"

# Load existing structured data if exists to skip already scraped subcategories
output_file = os.path.join(ITEM_URLS_DIR, "all_products_by_category.json")
if os.path.exists(output_file):
    with open(output_file, "r", encoding="utf-8") as f:
        structured_data = json.load(f)
else:
    structured_data = {}

all_urls = []
for main_cat in structured_data:
    for subcat in structured_data[main_cat]:
        all_urls.extend(structured_data[main_cat][subcat])

# ❌ Categories to skip
SKIP_CATEGORIES = {"Help", "FAQ", "Order Status", "Return Order", "New"}

def load_all_products(page):
    prev_count = -1
    attempts = 0
    max_attempts = 40
    while attempts < max_attempts:
        attempts += 1
        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
        btn = page.query_selector("button:has-text('Load more'), button.load-more")
        if btn:
            try:
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(3000)
            except Exception:
                pass
        html = page.content()
        curr_count = len(BeautifulSoup(html, "html.parser").select(PRODUCT_SELECTOR))
        if curr_count == prev_count:
            break
        prev_count = curr_count

def extract_urls(page):
    load_all_products(page)
    soup = BeautifulSoup(page.content(), "html.parser")
    product_divs = soup.select(PRODUCT_SELECTOR)
    urls = []
    for div in product_divs:
        a = div.find("a", class_="pname")
        if a and a.get("href"):
            href = a["href"]
            full = href if href.startswith("http") else f"https://www.newbalance.co.uk{href}"
            urls.append(full)
    return urls

# Try scraping a single subcategory URL with a proxy
def try_scrape_subcategory_url(page, subcat_url, main_cat, subcat_name):
    try:
        page.goto(subcat_url, timeout=60000)
        # Check for error page (e.g., "Oops, something went wrong")
        error_selectors = [
            'text="Oops, something went wrong"',
            'text="Something went wrong"',
            'text="Error"',
            'text="Page not found"',
            'h1:near(:text("404"))',
            'h1:near(:text("503"))'
        ]
        for selector in error_selectors:
            if page.query_selector(selector):
                print(f"   ⚠️ Error page detected at {subcat_url}: {selector}")
                return False  # Treat as proxy failure, switch proxy

        # Wait for product selector briefly to check if products exist
        try:
            page.wait_for_selector(PRODUCT_SELECTOR, timeout=10000)
        except TimeoutError:
            print(f"   ⚠️ No product URLs found for {subcat_url} (no {PRODUCT_SELECTOR})")
            return 'skip'  # No products, skip to next URL without switching proxy

        urls = extract_urls(page)
        if not urls:
            print(f"   ⚠️ No product URLs found for {subcat_url} after extraction")
            return 'skip'  # No products, skip to next URL without switching proxy

        structured_data[main_cat][subcat_name] = urls
        all_urls.extend(urls)
        return True
    except TimeoutError as e:
        print(f"   ⚠️ Timeout at {subcat_url}: {e}")
        return False  # Proxy failure, switch proxy
    except Exception as e:
        print(f"   ⚠️ Error at {subcat_url}: {e}")
        return False  # Proxy failure, switch proxy

# Load category URLs (nested)
category_file = os.path.join(ITEM_URLS_DIR, "newbalance_categories_filtered.json")
try:
    with open(category_file, "r", encoding="utf-8") as f:
        category_data = json.load(f)
except FileNotFoundError:
    print(f"❌ Category file '{category_file}' not found.")
    exit(1)

with sync_playwright() as pw:
    proxy_manager.reset()
    for main_cat, subcats in category_data.items():
        if main_cat.strip() in SKIP_CATEGORIES:
            print(f"❌ Skipping Main Category: {main_cat}")
            continue

        print(f"📁 Main Category: {main_cat}")
        if main_cat not in structured_data:
            structured_data[main_cat] = {}

        subcat_items = list(subcats.items())
        # [:MAX_SUBCATEGORY_URLS]
        for subcat_name, subcat_url in subcat_items:
            if subcat_name in structured_data[main_cat]:
                print(f"   ⚠️ Skipping already scraped subcategory: {subcat_name}")
                continue

            print(f"   ▶️ Subcategory: {subcat_name}")
            url_scraped = False
            proxy_manager.reset()  # Reset proxy rotation for each subcategory URL

            while proxy_manager.attempt < proxy_manager.max_retries:
                proxy_config = proxy_manager.get_next_proxy()
                if not proxy_config:
                    print(f"   ❌ No more proxies available for {subcat_url}")
                    break

                try:
                    browser = pw.chromium.launch(headless=False, proxy=proxy_config)
                    page = browser.new_page(viewport={"width": 1280, "height": 800})

                    result = try_scrape_subcategory_url(page, subcat_url, main_cat, subcat_name)
                    browser.close()

                    if result == True:
                        url_scraped = True
                        break  # Success, move to next subcategory URL
                    elif result == 'skip':
                        print(f"   ⚠️ Skipping subcategory {subcat_url} due to no product URLs.")
                        break  # Skip to next URL without switching proxy
                    else:
                        # Proxy failure, mark failed and try next proxy
                        proxy_manager.mark_current_proxy_failed()
                        continue

                except Exception as e:
                    print(f"   ❌ Failed with proxy {proxy_config['server']}: {e}")
                    proxy_manager.mark_current_proxy_failed()
                    browser.close()
                    continue

            if not url_scraped:
                print(f"   ❌ Failed to scrape {subcat_url} with all {proxy_manager.max_retries} proxies.")

# Save outputs
with open(os.path.join(ITEM_URLS_DIR, "all_products_by_category.json"), "w", encoding="utf-8") as f:
    json.dump(structured_data, f, indent=2)

with open(os.path.join(ITEM_URLS_DIR, "all_product_urls_list.json"), "w", encoding="utf-8") as f:
    json.dump({"total": len(all_urls), "urls": all_urls}, f, indent=2)

unique = list(set(all_urls))
with open(os.path.join(ITEM_URLS_DIR, "all_product_urls_set.json"), "w", encoding="utf-8") as f:
    json.dump({"unique_count": len(unique), "urls": unique}, f, indent=2)

print(f"✅ Done. Scraped: {len(all_urls)} | Unique: {len(unique)}")