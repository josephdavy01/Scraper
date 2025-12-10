import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

# Folder structure
BASE_DIR = os.path.join("UK", "data", datetime.today().strftime("%Y-%m-%d"))
ITEM_URLS_DIR = os.path.join(BASE_DIR, "item_urls")
os.makedirs(ITEM_URLS_DIR, exist_ok=True)

# Final data format
data = {}

# Scrape function using Firefox
def scrape():
    global data
    with sync_playwright() as p:
        browser = None
        try:
            # ✅ Launch Firefox instead of Chromium
            browser = p.firefox.launch(headless=False)  
            context= browser.new_context()
            page = context.new_page()
            
            # Increase timeout for page loading (60 seconds)
            page.goto("https://www.newbalance.co.uk", timeout=60000)
            page.wait_for_selector('li.nav-item[data-testid^="category-"]', timeout=30000)
            page.wait_for_timeout(3000)

            # Scroll entire page
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(3000)

            # Parse HTML
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
                                full_url = f"https://www.newbalance.co.uk/{href}" if href.startswith('/') else href
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
            print(f"⏰ Timeout: {e}")
            if browser:
                browser.close()
            return False

        except Exception as e:
            print(f"❌ Error: {e}")
            if browser:
                browser.close()
            return False


# Run the scraper
try:
    if scrape():
        # Save results
        file_path = os.path.join(ITEM_URLS_DIR, "newbalance_categories_filtered.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Category URLs saved to {file_path}")
    else:
        print("❌ Scraping failed.")
except Exception as e:
    print(f"❌ Failed to run scraper: {e}")
