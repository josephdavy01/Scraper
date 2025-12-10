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
        time.sleep(10)
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        #data = soup.find('section',{'class' : '_container_1homa_245'})
        tags=soup.find_all('li',{'class' : '_item_77ob7_311 _itemLevel2_77ob7_443 _hidden_77ob7_417'})
        result ={}
        for tag in tags:
            gender =tag.find('a',class_='_link_77ob7_339 _linkLevel2_77ob7_455')
            if not gender:
                continue
            gender_name =gender.text.strip().lower()
            result[gender_name] = {}
            subcat_ul=tag.find('ul',{'class' : '_items_77ob7_311 _itemsLevel3_77ob7_489'})
            if not subcat_ul:
                continue
            subcats=subcat_ul.find_all('a',{'class' : '_link_77ob7_339'})
            for subcat in subcats:
                subcat_name =subcat.text.strip().lower().replace(' ', '_')
                href=subcat.get('href','')
                full_url = urljoin(url,href) if href.startswith('/') else href
                result[gender_name][subcat_name] = full_url
        valid_keys = [ "women", "men", "kids", "shop all"]
        result = {k:v for k,v in result.items() if k in valid_keys}
        return result

def main():
    today_str = date.today().strftime('%Y-%m-%d')

    countries = {
        'USA': 'https://www.on.com/en-us',
        'UK': 'https://www.on.com/en-gb'
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