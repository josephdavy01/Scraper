import json
import os
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

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

    # Setup Firefox driver options
    options = Options()
    options.headless = False  # Change to True if you want headless mode
    service = FirefoxService()  # Assumes geckodriver in PATH or specify executable_path

    try:
        driver = webdriver.Firefox(service=service, options=options)
        driver.set_page_load_timeout(60)
        url = "https://www.levi.com/GB/en_GB/"
        driver.get(url)

        # Wait fixed time for page to fully load, can adjust or use explicit waits
        time.sleep(70)

        # Find main nav buttons by CSS selector
        main_nav_buttons = driver.find_elements(By.CSS_SELECTOR, "button.top-nav__item-btn")

        for btn in main_nav_buttons:
            cat_name = btn.text.strip()
            cat_upper = cat_name.upper()

            if cat_upper in skip_keys:
                continue

            logging.info(f"Processing category: {cat_name}")
            try:
                btn.click()
            except WebDriverException as e:
                logging.warning(f"Could not click button for {cat_name}: {e}")
                continue

            time.sleep(30)  # Wait for submenu to load

            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            subcat_data = {}

            # First layer: Quick links like "Men’s New Arrivals"
            quick_links = soup.find_all('li', class_='lsco-col-md-4')
            for li in quick_links:
                a_tag = li.find('a')
                if a_tag:
                    label = a_tag.get('aria-label') or a_tag.get_text(strip=True)
                    href = a_tag.get('href')
                    if label and href:
                        href = urljoin("https://www.levi.com/GB/en_GB/", href)
                        subcat_data[label] = href

            # Second layer: Subcategories like "Men’s Jeans" → "Slim Jeans"
            l2_sections = soup.find_all('div', attrs={'data-v-a7fd0c1f': True})
            for section in l2_sections:
                title_tag = section.find('h6', class_='l2-items__link')
                if not title_tag:
                    continue

                l2_title = title_tag.get_text(strip=True)
                l3_data = {}

                containers = section.find_all('div', class_='nav-l3__container')
                for container in containers:
                    li_tag = container.find('li')
                    if li_tag:
                        a_tag = li_tag.find('a')
                        if a_tag:
                            label = a_tag.get('aria-label') or a_tag.get_text(strip=True)
                            href = a_tag.get('href')
                            if label and href:
                                href = urljoin("https://www.levi.com/GB/en_GB/", href)
                                l3_data[label] = href

                if l3_data:
                    subcat_data[l2_title] = l3_data

            if subcat_data:
                data[cat_name] = subcat_data

        driver.quit()

        os.makedirs(folder_path, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logging.info(f"Category URLs saved to: {file_path}")
        return data

    except (TimeoutException, WebDriverException) as e:
        logging.error(f"Error extracting category URLs for {country}: {e}")
        if 'driver' in locals():
            driver.quit()
        return {}

if __name__ == "__main__":
    today_str = datetime.today().strftime('%Y-%m-%d')
    countries = ['UK']
    for country in countries:
        get_category_urls(country, today_str)
