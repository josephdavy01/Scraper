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

# --- Global Lock ---
write_lock = threading.Lock()

# --- Thread Local for Driver Reuse ---
thread_local = threading.local()

# --- Read Data Files ---
if os.path.exists(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url_duplicate_removed.json"):
    with open(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url_duplicate_removed.json", "r", encoding="utf-8") as file:
        data = json.load(file)
else:
    data = []

if os.path.exists(f"{WEBSITE_NAME}/COLOR_CODE/color_code.json"):
    with open(f"{WEBSITE_NAME}/COLOR_CODE/color_code.json", "r", encoding="utf-8") as file:
        color_code = json.load(file)
else:
    color_code = {"color_to_code": {}, "code_to_color": {}}

file_path = f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/product_details_data_url_completed.json"
if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        product_data_completed = json.load(file)
else:
    product_data_completed = []

# --- Helper Functions ---

def get_driver():
    if not hasattr(thread_local, "driver"):
        thread_local.driver = create_driver()
    return thread_local.driver

def recreate_driver():
    if hasattr(thread_local, "driver"):
        try:
            thread_local.driver.quit()
        except Exception as e:
            logging.error(f"Error closing driver: {e}")
    thread_local.driver = create_driver()

def append_to_json_file(filepath, new_data):
    with write_lock:
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=4)

        with open(filepath, 'r+', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []

            if not isinstance(existing_data, list):
                existing_data = [existing_data]

            existing_data.append(new_data)
            f.seek(0)
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
            f.truncate()

# --- Timeout Helper for Windows ---

class FuncTimeoutException(Exception):
    pass

def run_with_timeout(func, timeout):
    result = [None]
    exception = [None]

    def wrapper():
        try:
            result[0] = func()
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=wrapper)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        raise FuncTimeoutException("Function call timed out")
    if exception[0]:
        raise exception[0]
    return result[0]

# --- Core Function to Get Product Details ---

def get_product_details(gender, category, sub_cat_name, url, max_retries=3):
    if url in product_data_completed:
        return

    driver = get_driver()
    try:
        for attempt in range(max_retries):
            try:
                # --- Safe Load URL ---
                def safe_get():
                    driver.get(url)

                run_with_timeout(safe_get, timeout=20)

                # --- Safe Execute Script ---
                def safe_script():
                    return driver.execute_script('return window.__PRELOADED_STATE__')

                script_content = run_with_timeout(safe_script, timeout=15)

                if script_content:
                    product_data = script_content.get('product', {})
                else:
                    product_data = {}

                # --- Save Product Data ---
                append_to_json_file(
                    f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/RAW_DATA/{url.split('/')[-1]}.json",
                    product_data
                )
                append_to_json_file(
                    f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/product_details_data_url_completed.json",
                    url
                )

                # --- Break if success ---
                break

            except (FuncTimeoutException, Exception) as e:
                logging.warning(f"Attempt {attempt + 1} failed for URL: {url} | Error: {e}")
                recreate_driver()
                driver = get_driver()

                if attempt == max_retries - 1:
                    logging.error(f"All retry attempts failed for URL: {url}")

    except Exception as e:
        logging.error(f"Critical error for URL: {url} | Error: {e}")

# --- Run Threads ---

def run_in_threads():
    start_time = time.time()
    logging.info("Starting multi-threaded processing...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for outer_list in data:
            for item in outer_list:
                gender = item.get("gender")
                category = item.get("category")
                sub_cat_name = item.get("sub_cat_name")

                for url in item.get("url", []):
                    futures.append(
                        executor.submit(get_product_details, gender, category, sub_cat_name, url)
                    )

        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error in thread: {e}")

    # --- Close all drivers after work ---
    if hasattr(thread_local, "driver"):
        try:
            thread_local.driver.quit()
        except Exception as e:
            logging.error(f"Error closing driver: {e}")

    time_taken = time.time() - start_time
    logging.info(f"Multi-threaded processing completed in {time_taken:.2f} seconds.")
    return True

# --- Start Function ---

def start_step6():
    thread_task = run_in_threads()
    if thread_task:
        return True
    else:
        return False

if __name__ == "__main__":
    start_step6()