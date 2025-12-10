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

if os.path.exists(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url_duplicate_removed.json"):
    with open(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url_duplicate_removed.json", "r", encoding="utf-8") as file:
        data = json.load(file)
else:
    data = {}

file_path = f"{WEBSITE_NAME}/COLOR_CODE/color_code.json"

if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        color_code = json.load(file)
else:
    color_code = {
        "color_to_code": {},
        "code_to_color": {}
    }

def create_color_code(data):
    colors = set()

    for sublist in data:
        if not isinstance(sublist, list):
            continue

        for item in sublist:
            if not isinstance(item, dict):
                continue

            urls = item.get("url")

            if isinstance(urls, str):
                urls = [urls]
            elif not isinstance(urls, list):
                continue

            for url in urls:
                if isinstance(url, str) and "_" in url:
                    color = url.split("/")[-1].split("_")[-1]
                    colors.add(color)

    # Get existing code mappings
    color_to_code = color_code.get("color_to_code", {})
    code_to_color = color_code.get("code_to_color", {})

    # Find current max code
    existing_codes = code_to_color.keys()
    max_code = max([int(code) for code in existing_codes if code.isdigit()], default=0)

    # Add new colors
    for color in sorted(colors):
        if color not in color_to_code:
            max_code += 1
            code = f"{max_code:03}"
            color_to_code[color] = code
            code_to_color[code] = color

    # Save updated mappings
    color_code["color_to_code"] = color_to_code
    color_code["code_to_color"] = code_to_color

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(color_code, f, indent=4)


# Call the function
def start_step5():
    create_color_code(data)
    return True

if __name__ == "__main__":
    start_step5()