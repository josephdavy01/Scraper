import os
import json
import re
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
JSON_DATA_DIR = os.path.join(BASE_DIR, "json_data")
ITEM_URLS_DIR = os.path.join(BASE_DIR, "item_urls")
os.makedirs(JSON_DATA_DIR, exist_ok=True)

def sanitize_filename(name):
    # Replace invalid characters and ensure max length of 100
    name = re.sub(r'[\\/*?:"<>|]', "_", name.strip())
    return name[:100] if name else "unknown"

def extract_product_data(page_content):
    soup = BeautifulSoup(page_content, "html.parser")

    ld_json_data = {}
    for script_tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script_tag.string.strip())
            if isinstance(data, dict) and "name" in data:
                ld_json_data = data
                break
        except Exception:
            continue

    material_texts = [
        span.get_text(strip=True)
        for span in soup.find_all("span")
        if "material" in span.get_text(strip=True).lower()
        or "composition" in span.get_text(strip=True).lower()
    ]

    features = [
        li.get_text(strip=True)
        for div in soup.select("div.ecom-bullets")
        for li in div.find_all("li")
        if li.get_text(strip=True)
    ]

    composition_parts = material_texts + features
    composition = " | ".join(composition_parts) if composition_parts else None

    return {
        "ld_json": ld_json_data,
        "details": {
            "composition": composition,
            "features": features
        }
    }

# Try scraping a single URL with a proxy
def try_scrape_url(page, url, main_cat, sub_cat, idx, folder_path):
    try:
        page.goto(url, timeout=60000)
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
                print(f"   ⚠️ Error page detected at {url}: {selector}")
                return False  # Treat as proxy failure, switch proxy

        page.wait_for_timeout(5000)
        content = page.content()
        scraped_data = extract_product_data(content)

        # Check if product details are obtained (e.g., ld_json is not empty)
        if not scraped_data["ld_json"]:
            print(f"   ⚠️ No product details found at {url}")
            return 'skip'  # No details, skip to next URL without switching proxy

        # Determine filename: prefer name, then sku, then URL segment
        product_name = scraped_data["ld_json"].get("name", "").strip()
        product_id = scraped_data["ld_json"].get("sku", "").strip()
        if not product_name and not product_id:
            # Extract ID from URL (e.g., ML574EVB from /pd/574-Core/ML574EVB.html)
            url_parts = url.rstrip('/').split('/')
            product_id = url_parts[-1].split('.')[0] if url_parts[-1] else "unknown"

        filename_base = product_name if product_name else product_id
        filename = f"{sanitize_filename(filename_base)}.json"

        # Check if file already exists
        if os.path.exists(os.path.join(folder_path, filename)):
            print(f"   ⚠️ Skipping already scraped product: {url} ({filename})")
            return True  # Count as scraped, move to next URL

        scraped_data["url"] = url
        scraped_data["category"] = main_cat
        scraped_data["subcategory"] = sub_cat

        with open(os.path.join(folder_path, filename), "w", encoding="utf-8") as f:
            json.dump(scraped_data, f, indent=2)

        return True
    except TimeoutError as e:
        print(f"   ⚠️ Timeout at {url}: {e}")
        return False  # Proxy failure, switch proxy
    except Exception as e:
        print(f"   ⚠️ Error at {url}: {e}")
        return False  # Proxy failure, switch proxy

# Load product URLs (nested format)
category_file = os.path.join(ITEM_URLS_DIR, "all_products_by_category.json")
try:
    with open(category_file, "r", encoding="utf-8") as f:
        categories = json.load(f)
except FileNotFoundError:
    print(f"❌ Category file '{category_file}' not found.")
    exit(1)

print(f"🧾 Loaded categories and URLs for scraping.")

with sync_playwright() as pw:
    total_scraped = 0
    proxy_manager.reset()

    for main_cat, subcats in categories.items():
        for sub_cat, urls in subcats.items():
            if not isinstance(urls, list):
                continue

            print(f"\n📂 Scraping: {main_cat} > {sub_cat}")
            folder_path = os.path.join(JSON_DATA_DIR, sanitize_filename(main_cat), sanitize_filename(sub_cat))
            os.makedirs(folder_path, exist_ok=True)

            for idx, url in enumerate(urls):
                print(f"   🔍 [{idx}] Scraping: {url}")
                url_scraped = False
                proxy_manager.reset()  # Reset proxy rotation for each URL

                while proxy_manager.attempt < proxy_manager.max_retries:
                    proxy_config = proxy_manager.get_next_proxy()
                    if not proxy_config:
                        print(f"   ❌ No more proxies available for {url}")
                        break

                    try:
                        browser = pw.firefox.launch(headless=False)
                        page = browser.new_page()

                        result = try_scrape_url(page, url, main_cat, sub_cat, idx, folder_path)
                        browser.close()

                        if result == True:
                            total_scraped += 1
                            url_scraped = True
                            break  # Success, move to next URL
                        elif result == 'skip':
                            print(f"   ⚠️ Skipping URL {url} due to no product details.")
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
                    print(f"   ❌ Failed to scrape {url} with all {proxy_manager.max_retries} proxies.")

print(f"\n✅ Finished scraping {total_scraped} products.")