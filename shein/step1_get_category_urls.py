import json
import logging
import os, sys
import re
import threading
import time
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from glob import glob

import concurrent.futures

#multi threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Specify the path to the manually downloaded ChromeDriver
chrome_driver_path = 'chromedriver.exe'

#Common variables
error_log = []
WEBSITE_NAME = "SHEININDIA"
WEBSITE_URL = "https://www.sheinindia.in/"
time_stamp = datetime.now().strftime("%Y%m%d")
# time_stamp = "20250428"

os.makedirs(f"{WEBSITE_NAME}/CATEGORY/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/COLOR_CODE", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/RAW_DATA", exist_ok=True)

def create_driver():
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Suppress logs
    service = Service(log_path='NUL')  # 'NUL' for Windows, '/dev/null' for Linux/macOS

    driver = webdriver.Chrome(service=service, options=options)
    return driver

def log_error(message, website=None, category=None, subcategory=None, sub_sub=None, url=None):
    """Log errors with detailed information."""
    error_log.append({
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "subcategory": subcategory,
        "sub_subcategory": sub_sub,
        "url": url,
        "message": message,
        "website": website
    })

def start_step1():
    # Initialize the Chrome driver
    driver = create_driver()
    driver.get(WEBSITE_URL)
    driver.implicitly_wait(2)
    actions = ActionChains(driver)

    menu_data = {}
    error_log = []

    try:
        menu_items = driver.find_elements(By.CSS_SELECTOR, "li[data-test^='li-']")

        for menu in menu_items:
            try:
                data_test = menu.get_attribute("data-test")
                if data_test == "li-TRENDING":
                    continue  # Skip TRENDING

                actions.move_to_element(menu).perform()
                driver.implicitly_wait(2)

                category_name = data_test.replace("li-", "").strip()
                menu_data[category_name] = {}

                flyout = menu.find_element(By.CLASS_NAME, "menu-flyout")
                third_levels = flyout.find_elements(By.CLASS_NAME, "third-level")

                for level in third_levels:
                    try:
                        title_elem = level.find_element(By.CLASS_NAME, "title")
                        title_text = title_elem.text.strip()

                        try:
                            title_link = title_elem.find_element(By.TAG_NAME, "a").get_attribute("href")
                        except:
                            title_link = None

                        subcategories = {}
                        try:
                            items = level.find_elements(By.CSS_SELECTOR, ".items span a")
                            for item in items:
                                sub_name = item.text.strip()
                                sub_link = item.get_attribute("href")
                                subcategories[sub_name] = sub_link
                        except:
                            pass

                        menu_data[category_name][title_text] = {
                            "url": title_link,
                            "subcategories": subcategories
                        }

                    except Exception as e:
                        error_log.append(f"Error in subcategory: {str(e)}")
                        log_error(f"Error in subcategory title: {e}")
                        continue

            except Exception as e:
                error_log.append(f"Error in menu item: {str(e)}")
                log_error(f"Error in menu item: {e}")
                continue

        # Post-processing
        main_urls = set()
        for main_cat in menu_data.values():
            for subcat_data in main_cat.values():
                if subcat_data["url"]:
                    main_urls.add(subcat_data["url"])

        for main_cat in menu_data.values():
            for subcat_data in main_cat.values():
                subcat_data["subcategories"] = {
                    name: url for name, url in subcat_data["subcategories"].items()
                    if url not in main_urls
                }

        menu_data.update({"status": "success", "date": time_stamp})

        os.makedirs(f'{WEBSITE_NAME}/CATEGORY/{time_stamp}', exist_ok=True)
        json_file_path = f'{WEBSITE_NAME}/CATEGORY/{time_stamp}/sheinindia_category_urls.json'
        with open(json_file_path, "w", encoding='utf-8') as outfile:
            json.dump(menu_data, outfile, ensure_ascii=False, indent=4)

        os.makedirs(f"{WEBSITE_NAME}_ERROR_LOG", exist_ok=True)
        error_json_file_path = f'{WEBSITE_NAME}_ERROR_LOG/sheinindia_step1_error_log_{time_stamp}.json'
        with open(error_json_file_path, "w", encoding='utf-8') as outfile:
            json.dump(error_log, outfile, ensure_ascii=False, indent=4)

    finally:
        driver.quit()

    return True

if __name__ == "__main__":
    start_step1()