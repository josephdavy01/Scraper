import os
import json
from datetime import date,datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
from urllib.parse import urljoin
import logging
import random
import re
import unicodedata

today_str = date.today().strftime('%Y-%m-%d')

countries = {
    'UK': "https://uk.puma.com/uk/en",
}


USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
]

def sanitize_filename(name):
    if not name:
        return "unnamed"
    
    name = name.lower()
    replacements = {"'": "", '"': "", "–": "-", "—": "-", "&": "and", ",": "", ":": "", ";": "", "!": "", "?": "", "/": "-", "\\": "-", "|": "-", "*": "", "<": "", ">": "", "+": "plus", "=": "equals", "%": "percent", "@": "at", "#": "hash", "$": "dollar", "^": "", "~": "", "`": "", "₹": "rupees", "™": "", "®": "", "©": ""}
    
    for old, new in replacements.items():
        name = name.replace(old, new)
    name = ''.join(char for char in name if unicodedata.category(char)[0] != 'S' or char in ['-', '_'])
    name = unicodedata.normalize('NFD', name)
    name = ''.join(char for char in name if unicodedata.category(char) != 'Mn')
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[-_]+', '_', name)
    name = name.strip('_-')
    if not name:
        name = "unnamed"
    return name

def get_category_urls(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel='chrome',
            args=['--disable-blink-features=AutomationControlled']  
        )
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            extra_http_headers={'Accept-Language': 'en-US,en;q=0.9'}
        )
        page = context.new_page()
        
        page.goto(url)
        time.sleep(random.uniform(10, 15))
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        main_categories = soup.find_all("li", attrs={"data-test-id": "main-nav-category-item"})
        
        if not main_categories:
            logging.warning("No categories found - possibly blocked by Cloudflare")
            browser.close()
            return {}
            
        result = {}
        base_url = page.url
        
        for main in main_categories:
            main_link = main.find("a", attrs={"data-link-location": "top-nav-level-1"})
            if not main_link:
                continue
            
            main_name = sanitize_filename(main_link.get_text(strip=True))
            subcats = {}
            
            level_2_sections = main.find_all("ul", role="menu")
            for section in level_2_sections:
                section_header = section.find("a", attrs={"data-test-id": "top-nav-level-2-top"})
                section_name = ""
                if section_header:
                    section_name = sanitize_filename(section_header.get_text(strip=True)) + "_"
                
                sub_links = section.find_all("a", attrs={"data-test-id": "top-nav-level-3"})
                for sub_link in sub_links:
                    subcat_name = sub_link.get_text(strip=True)
                    subcat_url = urljoin(base_url, sub_link.get("href"))
                    if subcat_url != urljoin(base_url, main_link.get("href")):
                        base_key = sanitize_filename(subcat_name)
                        key = section_name + base_key if section_name else base_key
                        subcats[key] = subcat_url
            
            side_links = main.find_all("a", attrs={"data-test-id": "top-nav-level-2-side"})
            for side_link in side_links:
                subcat_name = side_link.get_text(strip=True)
                subcat_url = urljoin(base_url, side_link.get("href"))
                if subcat_url != urljoin(base_url, main_link.get("href")):
                    key = sanitize_filename(subcat_name)
                    subcats[key] = subcat_url
            
            subcats['shop_all'] = urljoin(base_url, main_link.get("href"))
            result[main_name] = subcats
        
        browser.close()
        return result

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    for country, url in countries.items():
        logging.info(f'Fetching {country} category URLs now')
        jsondata = get_category_urls(url)
        logging.info(f'{country} category found {len(jsondata)} categories')
        output_path = f'{country}/Data/{today_str}/Item_urls'
        os.makedirs(output_path, exist_ok=True)
        output_file = f'{output_path}/{country}_category_urls.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(jsondata, f, indent=4, ensure_ascii=False)
        logging.info(f'{country} category URLs fetched and saved to {output_file}')

if __name__ == "__main__":
    main()