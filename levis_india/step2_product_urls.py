import json
import os
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_product_urls(country, today_str):
    category_folder_path = os.path.join(country, 'data', today_str, 'item_urls')
    category_file_path = os.path.join(category_folder_path, 'Category_urls.json')
    product_file_path = os.path.join(category_folder_path, 'Product_urls.json')

    try:
        with open(category_file_path, 'r', encoding='utf-8') as f:
            category_data = json.load(f)
    except FileNotFoundError:
        logging.error(f"Category URLs file not found: {category_file_path}")
        return {}
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from: {category_file_path}")
        return {}

    product_data = {}

    for top_category, subcategories in category_data.items():
        logging.info(f"Processing top-level category: {top_category}")
        product_data[top_category] = {}

        for subcat_name, subcat_url in subcategories.items():
            logging.info(f" Launching Chrome for subcategory: {subcat_name} ({subcat_url})")
            product_urls = set()

            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False, channel='chrome')
                    page = browser.new_page()

                    current_url = subcat_url
                    page_number = 1

                    while True:
                        logging.info(f"Visiting page {page_number}: {current_url}")
                        page.goto(current_url)
                        page.wait_for_selector('div.mmc-loop-item.grid__item', timeout=10000)

                        # Scroll to bottom
                        logging.info(f"Scrolling to bottom on page {page_number}")
                        previous_height = 0
                        while True:
                            current_height = page.evaluate("() => document.body.scrollHeight")
                            if current_height == previous_height:
                                break
                            page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                            page.wait_for_timeout(2000)
                            previous_height = current_height

                        # Parse product links
                        soup = BeautifulSoup(page.content(), "html.parser")
                        product_cards = soup.find_all('div', class_='mmc-loop-item grid__item')
                        logging.info(f"Found {len(product_cards)} products on page {page_number}")

                        for card in product_cards:
                            a_tag = card.find('a', class_='mmc-card-title')
                            if a_tag and a_tag.get('href'):
                                product_urls.add(urljoin(current_url, a_tag.get('href')))

                        # Pagination
                        next_page = soup.find('a', {'rel': 'next'})
                        if next_page and next_page.get('href'):
                            current_url = urljoin(current_url, next_page.get('href'))
                            page_number += 1
                            page.wait_for_timeout(5000)
                        else:
                            break

                    browser.close()

                # Save data for this subcategory
                product_data[top_category][subcat_name] = list(product_urls)
                logging.info(f" Collected {len(product_urls)} products for {subcat_name}")

                # Save partial progress
                os.makedirs(category_folder_path, exist_ok=True)
                tmp_path = product_file_path + '.tmp'
                with open(tmp_path, 'w', encoding='utf-8') as tmp_f:
                    json.dump(product_data, tmp_f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, product_file_path)

            except TimeoutError:
                logging.error(f"Timeout while scraping {subcat_name}")
                product_data[top_category][subcat_name] = []
            except Exception as e:
                logging.error(f" Error scraping {subcat_name}: {e}")
                product_data[top_category][subcat_name] = []

    # Final save
    try:
        with open(product_file_path, 'w', encoding='utf-8') as f:
            json.dump(product_data, f, indent=2, ensure_ascii=False)
        logging.info(f"Final product URLs saved to: {product_file_path}")
    except Exception as e:
        logging.error(f" Failed to save final product data: {e}")

    return product_data

if __name__ == "__main__":
    today_str = datetime.today().strftime('%Y-%m-%d')
    brand = 'levis'
    countries = ['India']

    for country in countries:
        brand_name = f'{brand}_{country}'
        logging.info(f"Starting scrape for: {brand_name}")
        get_product_urls(brand_name, today_str)
        logging.info(f" Scrape finished for: {brand_name}")
