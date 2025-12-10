import os
import json
from collections import defaultdict
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

def load_json(filepath):
    with open(filepath, "r") as f:
        return json.load(f)

def get_sorted_date_folders(base_dir):
    return sorted([ 
        name for name in os.listdir(base_dir) 
        if os.path.isdir(os.path.join(base_dir, name)) and name.isdigit()
    ])

def compare_dicts(prev_data, curr_data, path=""):
    missing_urls = []

    for key, prev_value in prev_data.items():
        if key in ["date", "status"]:
            continue

        curr_value = curr_data.get(key, None)

        # Handle the case where the key is missing in the current data
        if curr_value is None:
            # If the key is missing in current data, check if it was a URL in the previous data
            if isinstance(prev_value, str) and prev_value != "null":
                missing_urls.append(f"missing url {prev_value} key path {path + key}")
        elif isinstance(prev_value, dict) and isinstance(curr_value, dict):
            # Recursively compare subcategories or other nested dictionaries
            missing_urls.extend(compare_dicts(prev_value, curr_value, path + key + "."))
        elif isinstance(prev_value, str) and prev_value != "null":
            # If the previous value is a URL and the current value is missing or null
            if curr_value == "null" or curr_value is None:
                missing_urls.append(f"missing url {prev_value} key path {path + key}")

    return missing_urls

def generate_comparison_reports(base_dir):
    date_folders = get_sorted_date_folders(base_dir)

    for i in range(1, len(date_folders)):
        prev_date = date_folders[i - 1]
        curr_date = date_folders[i]

        prev_path = os.path.join(base_dir, prev_date, "sheinindia_category_urls.json")
        curr_path = os.path.join(base_dir, curr_date, "sheinindia_category_urls.json")

        if not os.path.exists(prev_path) or not os.path.exists(curr_path):
            continue

        prev_data = load_json(prev_path)
        curr_data = load_json(curr_path)

        missing_urls = compare_dicts(prev_data, curr_data)

        report = {
            "compared_with": prev_date,
            "missing_urls": missing_urls
        }

        # Write report to CATEGORY/{curr_date}/comparison_report.json
        output_path = os.path.join(base_dir, curr_date, "comparison_report.json")
        with open(output_path, "w") as out_file:
            json.dump(report, out_file, indent=4)

        print(f"✓ Comparison report saved to: {output_path}")

# Example usage

def start_step2():
    # Assuming you have already run step1 and have the CATEGORY folder populated
    # You can call the function to generate comparison reports
    base_folder = f"{WEBSITE_NAME}/CATEGORY/"
    generate_comparison_reports(base_folder)
    return True
if __name__ == "__main__":
    start_step2()