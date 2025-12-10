import json
import os
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# List of top-level categories to skip
skip_keys = {
    "MY ACCOUNT",
    "CONTACT US",
    "HAMBURGER LEVI'S LOGO",
    "LEVI'S LOGO",
    "CART DRAWER",
    "BLOG"
}

def get_category_urls(country, today_str):
    folder_path = os.path.join(country, 'data', today_str, 'item_urls')
    file_path = os.path.join(folder_path, 'Category_urls.json')
    data = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, channel='chrome')
            page = browser.new_page()
            url = "https://levi.in/"
            page.goto(url)
            page.wait_for_timeout(5000)  # Wait for page to fully load
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            main_tag = soup.find('ul', {'class': 'list-menu list-menu--inline'})
            if main_tag:
                sub_tags = main_tag.find_all('li', {'class': 'tw-flex tw-items-center header-tab-hover'})
                for sub_tag in sub_tags:
                    # Get top-level category name
                    summary = sub_tag.find('summary', {'class': 'header__menu-item'})
                    if not summary:
                        continue
                    a_tag = summary.find('a')
                    if not a_tag:
                        continue
                    cat_name = a_tag.get_text(strip=True)
                    cat_upper = cat_name.upper()
                    if cat_upper in skip_keys:
                        continue
                    logging.info(f"Processing category: {cat_name}")

                    # Initialize dictionary for category data
                    flat_data = {}

                    # Find the menu wrapper for subcategories
                    menu_wrapper = sub_tag.find('div', {'class': 'tw-w-full tw-overflow-auto tw-flex tw-justify-center menu-wrapper scroll-bar-hide'})
                    if menu_wrapper:
                        # Handle simple subcategories (e.g., SALE, NEW ARRIVALS)
                        if cat_name in ["SALE", "NEW ARRIVALS", "Featured Collections"]:
                            menu_items = menu_wrapper.find_all('a', {'class': 'data-menu'})
                            for item in menu_items:
                                subcat_name = item.get_text(strip=True)
                                subcat_url = urljoin(url, item.get('href'))
                                flat_data[subcat_name] = subcat_url
                        else:
                            # Handle nested subcategories for MEN and WOMEN (only prefixed)
                            submenu_lists = sub_tag.find_all('ul', {'class': 'list-menu motion-reduce'})
                            for submenu in submenu_lists:
                                section_title_tag = submenu.find_previous('span', {'class': 'header__menu-item'})
                                if section_title_tag:
                                    section_title = section_title_tag.get_text(strip=True).upper()
                                    for li in submenu.find_all('li', {'class': 'child__menu header__menu-item'}):
                                        a_tag = li.find('a')
                                        if a_tag:
                                            label = a_tag.get_text(strip=True)
                                            href = urljoin(url, a_tag.get('href'))
                                            # Add prefixed subcategory name
                                            combined_key = f"{section_title}-{label}"
                                            flat_data[combined_key] = href

                    if flat_data:
                        data[cat_name] = flat_data

            browser.close()

            # Save to JSON
            os.makedirs(folder_path, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logging.info(f"Category URLs saved to: {file_path}")
            return data

    except Exception as e:
        logging.error(f"Error extracting category URLs for {country}: {e}")
        return {}

if __name__ == "__main__":
    today_str = datetime.today().strftime('%Y-%m-%d')
    # countries = ['India']
    # for country in countries:
    #     get_category_urls(country, today_str)
    # today_str = datetime.today().strftime('%Y-%m-%d')
    brand='levis'
    countries = ['India']
    for country in countries:
        brand_name=f'{brand}_{country}'
        get_category_urls(brand_name, today_str)