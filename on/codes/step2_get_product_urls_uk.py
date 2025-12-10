import os
import json
import time
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

class OnProductScraper:
    def __init__(self):
        self.count_data = []

    def parse_script(self, json_data):
        product_urls = set()
        if not isinstance(json_data, dict):
            return product_urls

        graph = json_data.get('@graph', [])
        for node in graph:
            if node.get('@type') == 'ItemList':
                for item in node.get('itemListElement', []):
                    group = item.get('item', {})
                    url = group.get('url')
                    if url:
                        product_urls.add(url)
                    for variant in group.get('hasVariant', []):
                        offer = variant.get('offers', {})
                        variant_url = offer.get('url') or variant.get('url')
                        if variant_url:
                            product_urls.add(variant_url)
        return product_urls

    def get_all_product_links(self, category_dict):
        final_data = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            for main_cat, subcats in category_dict.items():
                main_cat_key = main_cat.lower().replace(" ", "_")
                if main_cat_key not in final_data:
                    final_data[main_cat_key] = {}
                for subcat, url in subcats.items():
                    subcat_key = subcat.lower().replace(" ", "_")
                    combined_key = f"{main_cat_key}_{subcat_key}"
                    print(f"\nScraping: {main_cat} -> {subcat}")
                    paged_url = f"{url}?page=50" 
                    page.goto(paged_url, wait_until='domcontentloaded')
                    time.sleep(10)
                    soup = BeautifulSoup(page.content(), 'html.parser')
                    script = soup.find('script', id='json-ld', type='application/ld+json')
                    if not script:
                        print(f"No JSON-LD found for {main_cat} -> {subcat}")
                        continue
                    try:
                        data = json.loads(script.string)
                        urls = self.parse_script(data)
                        final_data[main_cat_key][combined_key] = list(urls)
                    except Exception as e:
                        print(f"Error parsing JSON for {main_cat}->{subcat}: {e}")
                        continue
        return final_data

    def save_to_json(self, out_file, validation_path, data, country):
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"\n Product links saved to: {out_file}")
        count_file = f'{validation_path}/{country}_product_counts.json'
        with open(count_file, 'w', encoding='utf-8') as f:
            json.dump(self.count_data, f, indent=4, ensure_ascii=False)
        print(f" Product counts saved to: {count_file}")

if __name__ == "__main__":
    countries = ['UK']
    today_str = datetime.today().strftime("%Y-%m-%d")
    

    for country in countries:
        base_path = f'{country}/Data/{today_str}/Item_urls'
        validation_path = f'{country}/Data/{today_str}/Validation'
        os.makedirs(base_path, exist_ok=True)
        os.makedirs(validation_path, exist_ok=True)
        out_file = f'{base_path}/{country}_product_urls.json'
        read_file = f'{base_path}/{country}_category_urls.json'

        if not os.path.exists(read_file):
            print(f"Category file not found for {country}: {read_file}")
            continue

        with open(read_file, 'r', encoding='utf-8') as f:
            category_data = json.load(f)

        scraper = OnProductScraper()
        all_product_links = scraper.get_all_product_links(category_data)
        scraper.save_to_json(out_file, validation_path, all_product_links, country)