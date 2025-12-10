import json
import logging
import os
import threading
import time
import random
import string
import tempfile
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

# --- Setup logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Paths and constants ---
chrome_driver_path = 'chromedriver.exe'  # Your ChromeDriver path

WEBSITE_NAME = "SHEININDIA"
WEBSITE_URL = "https://www.sheinindia.in/"
time_stamp = "20251101"

# Create necessary directories
os.makedirs(f"{WEBSITE_NAME}/CATEGORY/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/COLOR_CODE", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/RAW_DATA", exist_ok=True)

# --- Globals ---
error_log = []
write_lock = threading.Lock()
driver = None  # Single global driver instance

# --- Load product URLs ---
if os.path.exists(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url_duplicate_removed.json"):
    with open(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url_duplicate_removed.json", "r", encoding="utf-8") as file:
        data = json.load(file)
else:
    data = []

# --- Load color code ---
if os.path.exists(f"{WEBSITE_NAME}/COLOR_CODE/color_code.json"):
    with open(f"{WEBSITE_NAME}/COLOR_CODE/color_code.json", "r", encoding="utf-8") as file:
        color_code = json.load(file)
else:
    color_code = {"color_to_code": {}, "code_to_color": {}}

# --- Load completed product URLs ---
file_path = f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/product_details_data_url_completed.json"
if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        product_data_completed = json.load(file)
else:
    product_data_completed = []

# --- Load proxies from proxies.txt ---
def load_proxies(filename):
    proxies = []
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            proxy = line.strip()
            if proxy:
                proxies.append(proxy)
    return proxies

PROXY_LIST = load_proxies("proxies.txt")

def get_random_proxy():
    proxy = random.choice(PROXY_LIST)
    parts = proxy.strip().split(':')
    host = parts[0]
    port = parts[1]
    username = parts[2] if len(parts) > 2 and parts[2] else None
    password = parts[3] if len(parts) > 3 and parts[3] else None
    return host, port, username, password

# --- Create Chrome extension for authenticated proxy ---
def get_proxy_extension(username, password, host, port):
    import zipfile
    proxy_auth_plugin_path = tempfile.mktemp(suffix='.zip')
    manifest_json = '''
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }
    '''
    background_js = string.Template(
    """
    var config = {
            mode: "fixed_servers",
            rules: {
              singleProxy: {
                scheme: "http",
                host: "${host}",
                port: parseInt(${port})
              },
              bypassList: ["localhost"]
            }
          };
    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
    chrome.webRequest.onAuthRequired.addListener(
        function(details) {
            return {authCredentials: {username: "${user}", password: "${passw}"}};
        },
        {urls: ["<all_urls>"]},
        ['blocking']
    );
    """
    ).substitute(host=host, port=port, user=username or '', passw=password or '')
    with zipfile.ZipFile(proxy_auth_plugin_path, 'w') as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)
    return proxy_auth_plugin_path

# --- Create Selenium Chrome driver with proxy ---
def create_driver():
    global driver
    if driver is not None:
        try:
            driver.quit()
        except Exception as e:
            logging.error(f"Error closing existing driver: {e}")
    
    host, port, username, password = get_random_proxy()
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    if username and password:
        extension_file = get_proxy_extension(username, password, host, port)
        options.add_extension(extension_file)
    else:
        options.add_argument(f'--proxy-server=http://{host}:{port}')
    service = Service(log_path='NUL')  # Windows
    driver = webdriver.Chrome(service=service, options=options)
    logging.info(f"Created driver with proxy {host}:{port} (auth={bool(username)})")
    return driver

# --- Append data to JSON (thread-safe) ---
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

# --- Timeout related ---
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

# --- Error logging ---
def log_error(message, website=None, category=None, subcategory=None, sub_sub=None, url=None):
    error_log.append({
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "subcategory": subcategory,
        "sub_subcategory": sub_sub,
        "url": url,
        "message": message,
        "website": website
    })

# --- Core function to get product details with Access Denied handling ---
def get_product_details(gender, category, sub_cat_name, url, max_retries=3):
    global driver
    if url in product_data_completed:
        return

    if driver is None:
        driver = create_driver()

    for attempt in range(max_retries):
        try:
            def safe_get():
                driver.get(url)

            run_with_timeout(safe_get, timeout=20)

            # Check for Access Denied in page source
            page_source = driver.page_source.lower()
            if "access denied" in page_source or "forbidden" in page_source:
                logging.warning(f"Access denied for URL: {url} with current proxy. Trying new proxy.")
                driver = create_driver()  # Recreate driver with new proxy
                continue  # Retry with new proxy

            def safe_script():
                return driver.execute_script('return window.__PRELOADED_STATE__')

            script_content = run_with_timeout(safe_script, timeout=15)

            if not script_content or 'product' not in script_content:
                logging.warning(f"No product data found for URL: {url}. Skipping save.")
                return  # Do not save anything

            product_data = script_content.get('product', {})

            # Save product data
            append_to_json_file(
                f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/RAW_DATA/{url.split('/')[-1]}.json",
                product_data
            )
            append_to_json_file(
                f"{WEBSITE_NAME}/PRODUCT_DATA/{time_stamp}/product_details_data_url_completed.json",
                url
            )

            break  # Success, exit retry loop

        except (FuncTimeoutException, Exception) as e:
            logging.warning(f"Attempt {attempt + 1} failed for URL: {url} | Error: {e}")
            driver = create_driver()  # Recreate driver on failure
            if attempt == max_retries - 1:
                logging.error(f"All retry attempts failed for URL: {url}")

# --- Run scraper sequentially ---
def run_sequentially():
    global driver
    start_time = time.time()
    logging.info("Starting sequential processing with single browser...")

    try:
        for outer_list in data:
            for item in outer_list:
                gender = item.get("gender")
                category = item.get("category")
                sub_cat_name = item.get("sub_cat_name")
                for url in item.get("url", []):
                    try:
                        get_product_details(gender, category, sub_cat_name, url)
                    except Exception as e:
                        logging.error(f"Error processing URL {url}: {e}")
    finally:
        # Close the driver at the end
        if driver is not None:
            try:
                driver.quit()
                logging.info("Closed browser driver.")
            except Exception as e:
                logging.error(f"Error closing driver: {e}")
            driver = None

    elapsed = time.time() - start_time
    logging.info(f"Sequential processing completed in {elapsed:.2f} seconds.")
    return True

# --- Main entry ---
def start_step6():
    return run_sequentially()

if __name__ == "__main__":
    start_step6()
