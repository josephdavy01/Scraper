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

write_lock = threading.Lock()
thread_local = threading.local()

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(threadName)s - %(message)s",
    level=logging.INFO
)

# --- Read Category Data ---
if os.path.exists(f"{WEBSITE_NAME}/CATEGORY/{time_stamp}/sheinindia_category_urls.json"):
    with open(f"{WEBSITE_NAME}/CATEGORY/{time_stamp}/sheinindia_category_urls.json", "r", encoding="utf-8") as file:
        category_data = json.load(file)
    del category_data['status']
    del category_data['date']
else:
    category_data = {}

file_path_category_completed = f"{WEBSITE_NAME}/CATEGORY/{time_stamp}/category_url_completed.json"
if os.path.exists(file_path_category_completed):
    with open(file_path_category_completed, "r", encoding="utf-8") as file:
        category_data_completed = json.load(file)
else:
    category_data_completed = []

# --- Helper Functions ---
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

def flatten_shein_data(data):
    flat_data = []
    for gender, categories in data.items():
        for category_name, category_info in categories.items():
            category_url = category_info.get("url")
            subcategories = category_info.get("subcategories", {})

            item = {
                "gender": gender,
                "category": category_name,
                "category_url": category_url,
                "subcategories": []
            }

            for sub_name, sub_url in subcategories.items():
                item["subcategories"].append({
                    "sub_cat_name": sub_name,
                    "sub_cat_url": sub_url
                })

            if not item["subcategories"]:
                item["subcategories"] = None

            flat_data.append(item)

    return flat_data

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

def scroll_to_bottom(driver, wait_time=1, max_attempts=10):
    last_height = driver.execute_script("return document.body.scrollHeight")
    attempts = 0

    while attempts < max_attempts:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)
        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            attempts += 1
        else:
            attempts = 0

        last_height = new_height

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

def process_products(gender, category, category_url=None, sub_cat_name=None, sub_cat_url=None):
    product_urls = []
    urls = []
    product_details = {}

    if category_url:
        url = category_url
    elif sub_cat_url:
        url = sub_cat_url

    if url in category_data_completed:
        logging.info(f"URL already processed: {url}")
        return

    driver = get_driver()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logging.info(f"Starting scraping URL: {url}")
            run_with_timeout(lambda: driver.get(url), timeout=30)
            scroll_to_bottom(driver)

            total_class = driver.find_element(By.CLASS_NAME, "length")
            total_products_text = total_class.find_element(By.TAG_NAME, "strong").text.strip()
            total_products = int(total_products_text.split()[0].replace(",", ""))  # Handle commas

            product = driver.find_element(By.CLASS_NAME, "ReactVirtualized__Grid__innerScrollContainer")
            products = product.find_elements(By.CSS_SELECTOR, ".item.rilrtl-products-list__item.item")

            for prd in products:
                try:
                    product_link = prd.find_element(By.TAG_NAME, "a").get_attribute("href")
                    urls.append(product_link)
                except NoSuchElementException:
                    logging.error(f"Product link not found in {url}")
                    continue

            product_details = {
                "gender": gender,
                "category": category,
                "sub_cat_name": sub_cat_name,
                "product_count_from_url": total_products,
                "product_count_found": len(urls),
                "url": urls
            }
            product_urls.append(product_details)

            # Check if the product counts match
            if len(urls) == total_products:
                break  # Success, the counts match
            if len(urls) != total_products:
                logging.warning(f"Mismatch between total products ({total_products}) and found products ({len(urls)})")
                break
            
            # If retry count is exhausted, take the last result
            if attempt == max_retries - 1:
                logging.error(f"All retry attempts failed for URL: {url}. Using the last scraped result.")

        except (FuncTimeoutException, Exception) as e:
            logging.warning(f"Attempt {attempt + 1} failed for URL: {url} | Error: {e}")
            recreate_driver()
            driver = get_driver()

    # If we exit the retry loop and the counts match, append to the JSON files
    if len(urls) == total_products:
        append_to_json_file(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url.json", product_urls)
        append_to_json_file(f"{WEBSITE_NAME}/CATEGORY/{time_stamp}/category_url_completed.json", url)

def run_in_threads(flat_data):
    start_time = time.time()
    logging.info("Starting multi-threaded processing...")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for item in flat_data:
            gender = item['gender']
            category = item['category']
            category_url = item.get('category_url')
            subcategories = item.get('subcategories')

            if category_url:
                futures.append(
                    executor.submit(process_products, gender, category, category_url)
                )

            if subcategories:
                for subcat in subcategories:
                    sub_cat_name = subcat.get('sub_cat_name')
                    sub_cat_url = subcat.get('sub_cat_url')
                    futures.append(
                        executor.submit(process_products, gender, category, None, sub_cat_name, sub_cat_url)
                    )

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error in thread: {e}")

    if hasattr(thread_local, "driver"):
        try:
            thread_local.driver.quit()
        except Exception as e:
            logging.error(f"Error closing driver: {e}")

    time_taken = time.time() - start_time
    logging.info(f"Multi-threaded processing completed in {time_taken:.2f} seconds.")

def start_step3():
    flat_data = flatten_shein_data(category_data)
    run_in_threads(flat_data)
    return True

if __name__ == "__main__":
    start_step3()