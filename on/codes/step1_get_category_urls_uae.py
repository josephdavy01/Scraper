import os
import json
import time
import logging
from datetime import date
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_category_urls(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        time.sleep(5)
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')

        result = {}
       
        menu = soup.find('ul', class_='submenu submenu-1')
        if not menu:
            return result

        for li in menu.find_all('li', recursive=False):
            a_tag = li.find('a', class_='submenu-1-link')
            if not a_tag:
                continue
            gender_name = a_tag.text.strip().lower()
            gender_key = gender_name.replace(' ', '_') if gender_name != "shop all" else "shop all"
            if gender_key not in ["women", "men", "kids", "shop all"]:
                continue

            result[gender_key] = {}
            submenu = li.find('ul', class_='submenu submenu-2')
            if submenu:
                for sub_li in submenu.find_all('li', class_='no-submenu', recursive=False):
                    sub_a = sub_li.find('a')
                    if not sub_a:
                        continue
                    subcat_name = sub_a.text.strip().lower().replace(' ', '_')
                    href = sub_a.get('href', '')
                    full_url = urljoin(url, href) if href.startswith('/') else href
                    result[gender_key][subcat_name] = full_url

        return result

def main():
    today_str = date.today().strftime('%Y-%m-%d')

    countries = {
        'UAE': 'https://on.ae'
    }

    for country, url in countries.items():
        logging.info(f'Fetching {country} category URLs now')
        jsondata = get_category_urls(url)

        output_path = f'{country}/Data/{today_str}/Item_urls'
        os.makedirs(output_path, exist_ok=True)
        output_file = f'{output_path}/{country}_category_urls.json'

        with open(output_file, 'w') as f:
            json.dump(jsondata, f, indent=4)

        logging.info(f'{country} category URLs fetched and saved to {output_file}')
        logging.info(f'Found {len(jsondata)} categories for {country}')

if __name__ == "__main__":
    main()