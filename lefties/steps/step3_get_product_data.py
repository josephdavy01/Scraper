import os
import json
import logging
import re
import time
from pathlib import Path
from curl_cffi import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from filelock import FileLock

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_product_json(data, country, gender, category, pid, today_date):
    """Saves product data to a JSON file."""
    output_path = Path(country) / today_date / 'Json_data' / gender / category
    output_path.mkdir(parents=True, exist_ok=True)
    
    file_path = output_path / f"{pid}.json"
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save JSON for PID {pid} in {country}: {e}")

def get_product_data_from_api(pid, country, store_id, country_config):
    """Fetches product data for a single PID using curl_cffi with retries."""
    url = f'https://www.lefties.com/itxrest/3/catalog/store/{store_id}/productsArray?productIds={pid}&languageId=-1&appId=1'
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
                headers=headers,
                proxies=proxies,
                impersonate="chrome120",
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if data and data.get('products'):
                return pid, data, True
            else:
                logging.warning(f"No product data for PID {pid} in {country}. Attempt {attempt + 1}/{max_retries}.")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return pid, None, True 

        except requests.errors.RequestsError as e:
            if hasattr(e, 'response') and e.response and e.response.status_code == 404:
                logging.warning(f"Product {pid} in {country} not found (404).")
                return pid, None, True
            logging.error(f"HTTP error for PID {pid} in {country} (Attempt {attempt + 1}/{max_retries}): {e}")
        except Exception as e:
            logging.error(f"Error fetching data for PID {pid} in {country} (Attempt {attempt + 1}/{max_retries}): {e}")

        if attempt < max_retries - 1:
            time.sleep(2)
        else:
            return pid, None, False

    return pid, None, False

def process_country(country, config, today_date, re_run):
    """Processes a single country to fetch product data."""
    country_config = config[country]
    store_id = country_config['store_id']
    
    json_data_dir = Path(country) / today_date / 'Json_data'
    json_data_dir.mkdir(parents=True, exist_ok=True)
    
    lock_file_path = json_data_dir / f'{country}_scrape_log.json.lock'
    lock = FileLock(lock_file_path, timeout=10)
    log_file = json_data_dir / f'{country}_scrape_log.json'

    pids_file = Path(country) / today_date / 'Item_urls' / f'{country}_product_links.json'
    
    if not pids_file.exists():
        logging.warning(f"Product links file not found for {country} at {pids_file}. Skipping.")
        return 'skipped'

    try:
        with open(pids_file, 'r', encoding='utf-8') as f:
            pids_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Could not read product links file for {country}: {e}")
        return 'failed'

    scraped_log = {}
    if log_file.exists() and not re_run:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                scraped_log = json.load(f)
        except json.JSONDecodeError:
            pass

    tasks = []
    for gender, categories in pids_data.items():
        for category, urls in categories.items():
            for url in urls:
                pid_str = None
                # First, try the format with "-p<PID>.html"
                match = re.search(r'p(\d+)\.html', url)
                if match:
                    pid_str = match.group(1)
                else:
                    # If that fails, try to get a numeric ID from the end of the URL path
                    # Example: https://www.lefties.com/es/en/690865019
                    match = re.search(r'/(\d+)$', url.split('?')[0].rstrip('/'))
                    if match:
                        pid_str = match.group(1)
                
                if pid_str:
                    if pid_str not in scraped_log or scraped_log.get(pid_str) != 'success':
                        tasks.append({'pid': pid_str, 'gender': gender, 'category': category})
                else:
                    logging.warning(f"Could not extract PID from URL: {url}")
    
    if not tasks:
        logging.info(f"All products already scraped for {country}. Skipping.")
        return 'success'

    logging.info(f"Found {len(tasks)} products to scrape for {country}.")
    max_workers = country_config.get('browsers_product_urls', 4)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_info = {
            executor.submit(get_product_data_from_api, task['pid'], country, store_id, country_config): task
            for task in tasks
        }
        
        for future in as_completed(future_to_info):
            task_info = future_to_info[future]
            pid = task_info['pid']
            
            try:
                pid_result, data, is_final = future.result()
                
                status_to_log = 'failure'
                if is_final and data:
                    save_product_json(data, country, task_info['gender'], task_info['category'], pid_result, today_date)
                    status_to_log = 'success'
                
                with lock:
                    current_log = {}
                    if log_file.exists():
                        try:
                            with open(log_file, 'r', encoding='utf-8') as f:
                                current_log = json.load(f)
                        except json.JSONDecodeError:
                            pass
                            
                    current_log[str(pid_result)] = status_to_log
                    
                    with open(log_file, 'w', encoding='utf-8') as f:
                        json.dump(current_log, f, indent=4)
                
                if status_to_log == 'success':
                    logging.info(f"Scraped PID {pid_result} for {task_info['gender']} > {task_info['category']} ({country})")
                else:
                    logging.warning(f"Failed to scrape PID {pid_result} for {task_info['gender']} > {task_info['category']} ({country}).")

            except Exception as e:
                logging.error(f"Error processing future for PID {pid}: {e}")
                with lock:
                    current_log = {}
                    if log_file.exists():
                        try:
                            with open(log_file, 'r', encoding='utf-8') as f:
                                current_log = json.load(f)
                        except json.JSONDecodeError:
                            pass
                    current_log[str(pid)] = 'failure'
                    with open(log_file, 'w', encoding='utf-8') as f:
                        json.dump(current_log, f, indent=4)
    return 'success'

def get_product_data(config, today_date, re_run=False):
    """
    Main function to orchestrate fetching product data for all countries concurrently.
    """
    countries = list(config.keys())
    country_statuses = {}
    
    with ThreadPoolExecutor(max_workers=len(countries) or 1) as executor:
        future_to_country = {executor.submit(process_country, c, config, today_date, re_run): c for c in countries}
        for future in as_completed(future_to_country):
            country = future_to_country[future]
            try:
                status = future.result()
                country_statuses[country] = status
            except Exception as exc:
                logging.error(f'{country} generated an exception: {exc}')
                country_statuses[country] = 'failed'

    return country_statuses
