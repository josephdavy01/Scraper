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
# time_stamp = datetime.now().strftime("%Y%m%d")
time_stamp = "20251101"

os.makedirs(f"{WEBSITE_NAME}/CATEGORY/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/COLOR_CODE", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/RAW_DATA", exist_ok=True)

# def create_driver():
#     chrome_options = Options()
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_argument("--headless")  # Run in headless mode
#     service = ChromeService(executable_path=chrome_driver_path)
#     return webdriver.Chrome(service=service, options=chrome_options)
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
from copy import deepcopy

if os.path.exists(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url.json"):
    with open(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url.json", "r", encoding="utf-8") as file:
        data = json.load(file)
else:
    data = {}

json_file_path = f'{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url_duplicate_removed.json'
removed_product_urls = f'{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url_removed_list.json'

def remove_global_duplicate_urls(data):
    from collections.abc import Iterable
    from copy import deepcopy

    result = deepcopy(data)
    seen_urls = set()
    removed_urls_log = []

    for sublist in result:
        for entry in sublist:
            if not isinstance(entry, dict):
                continue  # Skip if not a dict

            urls = entry.get('url')

            # Normalize the URL field
            if not urls:
                urls = []
            elif isinstance(urls, str):
                urls = [urls]
            elif not isinstance(urls, Iterable) or isinstance(urls, dict):
                urls = []

            unique_urls = []
            removed_urls = []

            for url in urls:
                if url and url not in seen_urls:
                    unique_urls.append(url)
                    seen_urls.add(url)
                elif url:
                    removed_urls.append(url)

            entry['url'] = unique_urls
            entry['product_count_after_dup_remove'] = len(unique_urls)
            entry['url_removed_count'] = len(removed_urls)

            if removed_urls:
                removed_urls_log.append({
                    "gender": entry.get("gender"),
                    "category": entry.get("category"),
                    "sub_cat_name": entry.get("sub_cat_name"),
                    "url_removed": removed_urls,
                    "url_removed_count": len(removed_urls)
                })

    return result, removed_urls_log


def cleaned_data():
    cleaned_data, removed_urls = remove_global_duplicate_urls(data)
    # Save the collected data to a JSON file
    with open(json_file_path, "w", encoding='utf-8') as outfile:
        json.dump(cleaned_data, outfile, ensure_ascii=False, indent=4)

    with open(removed_product_urls, "w", encoding='utf-8') as outfile:
        json.dump(removed_urls, outfile, ensure_ascii=False, indent=4)

    return cleaned_data, removed_urls

def start_step4():
    # Check if both files exist
    if os.path.exists(json_file_path) and os.path.exists(removed_product_urls):
        with open(removed_product_urls, 'r') as f:
            try:
                removed_data = json.load(f)
            except json.JSONDecodeError:
                print("Error decoding JSON. Skipping...")
                return False

        if not removed_data:  # Checks if dict is empty
            print("Removed product URLs file is empty.")
            cleaned_data()
            return True
        else:
            print("Duplicate removal already done. Skipping...")
            return True
    else:
        cleaned_data()

        return True
    
if __name__ == "__main__":
    start_step4()