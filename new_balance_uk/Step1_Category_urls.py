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
proxy_manager = ProxyManager(hardcoded_proxy, proxy_file="proxies.txt")

# Folder structure
BASE_DIR = os.path.join("UK", "data", datetime.today().strftime("%Y-%m-%d"))
ITEM_URLS_DIR = os.path.join(BASE_DIR, "item_urls")
os.makedirs(ITEM_URLS_DIR, exist_ok=True)

# Check if output file already exists
output_file = os.path.join(ITEM_URLS_DIR, "newbalance_categories_filtered.json")
if os.path.exists(output_file):
    print(f"⚠️ Output file '{output_file}' already exists. Skipping category scraping.")
    exit(0)

# Final data format
data = {}

# Scrape function with proxy attempt
def try_scrape_with_proxy(proxy_config):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False, proxy=proxy_config)
            page = browser.new_page()
            page.goto("https://www.newbalance.co.uk", timeout=60000)
            page.wait_for_selector('li.nav-item[data-testid^="category-"]', timeout=30000)
            page.wait_for_timeout(3000)

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            soup = BeautifulSoup(page.content(), "html.parser")
            nav_items = soup.find_all('li', class_='nav-item')

            for item in nav_items:
                label_tag = item.find('span', class_='nav-label')
                if not label_tag:
                    continue

                top_category = label_tag.text.strip()
                if top_category not in data:
                    data[top_category] = {}

                dropdown_items = item.find_all('li', class_='dropdown-item')
                level2_items = [li for li in dropdown_items if li.find('a', class_='dropdown-link dropdown-toggle')]

                if level2_items:
                    for level2_li in level2_items:
                        level2_link = level2_li.find('a', class_='dropdown-link dropdown-toggle')
                        level2_name = level2_link.text.strip()

                        level3_links = level2_li.find_all('a', class_='dropdown-link')
                        for lvl3 in level3_links:
                            if 'dropdown-toggle' in lvl3.get('class', []):
                                continue
                            name = lvl3.text.strip()
                            href = lvl3.get('href')
                            if name and href:
                                full_url = f"https://www.newbalance.co.uk{href}" if href.startswith('/') else href
                                sub_key = f"{level2_name}-{name}"
                                data[top_category][sub_key] = full_url
                else:
                    direct_links = item.find_all('a', class_='dropdown-link')
                    for link in direct_links:
                        name = link.text.strip()
                        href = link.get('href')
                        if name and href:
                            full_url = f"https://www.newbalance.co.uk{href}" if href.startswith('/') else href
                            sub_key = name
                            data[top_category][sub_key] = full_url

            browser.close()
            return True
        except TimeoutError as e:
            print(f"Timeout with proxy {proxy_config['server']}: {e}")
            browser.close()
            return False
        except Exception as e:
            print(f"Error with proxy {proxy_config['server']}: {e}")
            browser.close()
            return False

# Run the scraper with proxy rotation
try:
    proxy_manager.reset()
    while proxy_manager.attempt < proxy_manager.max_retries:
        proxy_config = proxy_manager.get_next_proxy()
        if not proxy_config:
            break
        if try_scrape_with_proxy(proxy_config):
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Category URLs saved to {output_file}")
            break
        proxy_manager.mark_current_proxy_failed()
    else:
        print(f"❌ Failed after trying all {proxy_manager.max_retries} proxies.")
        exit(1)
except Exception as e:
    print(f"❌ Failed to run scraper: {e}")
    exit(1)