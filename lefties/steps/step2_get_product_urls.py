import os
import json
import logging
import time
from pathlib import Path
from curl_cffi import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from filelock import FileLock

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_product_urls_from_category(category_details, country, store_id, country_config):
    """Fetches product URLs for a single category using curl_cffi with retries."""
    category_id = category_details['id']
    
    # url = f'https://www.lefties.com/itxrest/3/catalog/store/{store_id}/category/{category_id}/product'
    url = f'https://www.lefties.com/itxrest/3/catalog/store/{store_id}/category/{category_id}/product?showProducts=false&languageId=-1&appId=1'
    params = {'showProducts': 'true', 'languageId': '-1', 'appId': '1'}
    headers = {
        'Accept': '*/*',
        'Content-Type': 'application/json',
        'Connection': 'keep-alive',
    }

    proxies = None
    if country_config.get('use_proxies'):
        proxy_info = country_config.get('proxies')
        if proxy_info:
            proxy_url = f"http://{proxy_info['username']}:{proxy_info['password']}@{proxy_info['server']}"
            proxies = {"http": proxy_url, "https": proxy_url}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                proxies=proxies,
                impersonate="chrome120",
                timeout=30
            )

            if response.status_code == 404:
                logging.warning(f"Category {category_id} in {country} not found (404). Attempt {attempt + 1}/{max_retries}.")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                # After retries, if still 404, treat as flaky (return False for is_final)
                # User reported 404s can be temporary.
                return category_id, [], False

            response.raise_for_status()
            data = response.json()
            
            product_urls = []
            products = data.get('products', [])
            
            # If we got products, it's a success
            if products:
                for product in products:
                    product_url_path = None
                    if isinstance(product, dict):
                        product_url_path = product.get('productUrl')
                    elif isinstance(product, str):
                        product_url_path = product
                    else:
                        logging.warning(f"Unexpected data format for product in category {category_id}. Expected dict or str, got {type(product)}.")

                    if product_url_path:
                        full_url = f"{country_config['base_url']}/{product_url_path}"
                        product_urls.append(full_url)
                
                return category_id, product_urls, True
            
            # If 0 products, retry
            logging.info(f"Category {category_id} returned 0 products. Attempt {attempt + 1}/{max_retries}.")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            
            # If still 0 products after retries, assume it's truly empty
            return category_id, [], True

        except Exception as e:
            logging.error(f"Error fetching products for category {category_id} in {country} (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return category_id, None, False

    return category_id, None, False

def process_country(country, config, today_date, re_run):
    """Processes a single country to fetch product URLs."""
    country_config = config[country]
    store_id = country_config['store_id']
    
    output_dir = Path(country) / today_date / 'Item_urls'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    lock_file_path = output_dir / f'{country}_product_links.json.lock'
    lock = FileLock(lock_file_path, timeout=10)

    output_file = output_dir / f'{country}_product_links.json'
    log_file = output_dir / f'{country}_product_log.json'

    # Initial check if completely done (optional, but good optimization)
    # But we need to load partial progress anyway, so we skip the "return if output_file exists" check
    # unless we are sure it's 100% complete. For now, we rely on the log file.

    category_file = Path(country) / today_date / 'Category' / f'{country}_category.json'
    if not category_file.exists():
        logging.warning(f"Category file not found for {country}. Skipping.")
        return
        
    with open(category_file, 'r', encoding='utf-8') as f:
        categories_data = json.load(f)

    scraped_log = {}
    if log_file.exists() and not re_run:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                scraped_log = json.load(f)
        except json.JSONDecodeError:
            pass

    tasks = []
    for gender, subcategories in categories_data.items():
        for category_name, category_details in subcategories.items():
            cat_id_str = str(category_details['id'])
            if cat_id_str not in scraped_log or scraped_log.get(cat_id_str) != 'success':
                tasks.append((gender, category_name, category_details))

    if not tasks:
        logging.info(f"All categories already scraped for {country}. Skipping.")
        return

    max_workers = country_config.get('browsers_product_urls', 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_info = {
            executor.submit(get_product_urls_from_category, details, country, store_id, country_config): (gender, cat_name, details)
            for gender, cat_name, details in tasks
        }
        
        for future in as_completed(future_to_info):
            gender, cat_name, task_details = future_to_info[future]
            try:
                cat_id, urls, is_final = future.result()
                
                if is_final:
                    # Acquire lock only for the writing part
                    with lock:
                        # 1. Load existing data
                        current_data = {}
                        if output_file.exists():
                            try:
                                with open(output_file, 'r', encoding='utf-8') as f:
                                    current_data = json.load(f)
                            except json.JSONDecodeError:
                                pass
                        
                        # 2. Update data
                        if gender not in current_data:
                            current_data[gender] = {}
                        
                        # Even if urls is empty, we save it if it's final (truly empty)
                        if urls:
                            current_data[gender][cat_name] = urls
                            # 3. Write data back
                            with open(output_file, 'w', encoding='utf-8') as f:
                                json.dump(current_data, f, indent=4)
                            
                        # 4. Update log
                        # Reload log to be safe
                        current_log = {}
                        if log_file.exists():
                            try:
                                with open(log_file, 'r', encoding='utf-8') as f:
                                    current_log = json.load(f)
                            except json.JSONDecodeError:
                                pass
                                
                        current_log[str(cat_id)] = 'success'
                        
                        with open(log_file, 'w', encoding='utf-8') as f:
                            json.dump(current_log, f, indent=4)
                            
                        logging.info(f"Saved {len(urls) if urls else 0} urls for {gender} > {cat_name} ({country})")
                else:
                    logging.warning(f"Category {cat_id} ({gender} > {cat_name}) was flaky/failed. Not marking as success.")
                    with lock:
                        # Reload log to be safe
                        current_log = {}
                        if log_file.exists():
                            try:
                                with open(log_file, 'r', encoding='utf-8') as f:
                                    current_log = json.load(f)
                            except json.JSONDecodeError:
                                pass
                                
                        current_log[str(cat_id)] = 'failure'
                        
                        with open(log_file, 'w', encoding='utf-8') as f:
                            json.dump(current_log, f, indent=4)

            except Exception as e:
                cat_id = task_details['id']
                logging.error(f"Category {cat_id} ({gender} > {cat_name}) failed: {e}")
                with lock:
                    # Reload log to be safe
                    current_log = {}
                    if log_file.exists():
                        try:
                            with open(log_file, 'r', encoding='utf-8') as f:
                                current_log = json.load(f)
                        except json.JSONDecodeError:
                            pass
                            
                    current_log[str(cat_id)] = 'failure'
                    
                    with open(log_file, 'w', encoding='utf-8') as f:
                        json.dump(current_log, f, indent=4)

def get_product_urls(config, today_date, re_run=False):
    """
    Main function to orchestrate fetching product URLs for all countries concurrently.
    """
    countries = list(config.keys())
    with ThreadPoolExecutor(max_workers=len(countries) or 1) as executor:
        executor.map(lambda c: process_country(c, config, today_date, re_run), countries)