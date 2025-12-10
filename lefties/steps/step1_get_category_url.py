import os
import logging
import json
from curl_cffi import requests
import time
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)

def get_category_ids_from_api(country, store_id, country_config):
    """Fetches category data from the API for a given store with retries and proxy support."""
    url = f'https://www.lefties.com/itxrest/2/catalog/store/{store_id}/category'
    params = {
        'languageId': '-1',
        'typeCatalog': '1',
        'appId': '1'
    }
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

    for attempt in range(3):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                proxies=proxies,
                timeout=20,
                impersonate="chrome120"
            )
            if response.status_code != 200:
                logging.error(f"Status Code: {response.status_code}")
                logging.error(f"Request Headers: {response.request.headers}")
                logging.error(f"Response: {response.text[:200]}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/3 failed for {country} ({store_id}): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    
    logging.error(f"All attempts failed for {country}. Skipping.")
    return None

def process_category_data(json_data, base_url):
    """Processes the raw category JSON data to extract URLs and IDs."""
    processed_data = {}
    if not json_data or 'categories' not in json_data:
        return processed_data

    for i in json_data['categories']:
        processed_data[i['nameEn']] = {}

        if i['nameEn'] in ['Woman', 'Man']:
            for j in i['subcategories']:
                subcat = j.get('subcategories')
                if subcat:
                    for k in j['subcategories']:
                        if k['nameEn'] not in ['-', 'View All']:
                            category = f"{j['nameEn'].lower().split(' ')[-1]}_{k['nameEn'].lower().replace(' ', '-').replace('|', '&')}"
                            url = f"{base_url}/{i['nameEn']}/{j['nameEn'].replace('/', '-')}/{k['nameEn']}-c{k['id']}.html".lower().replace(' ', '-').replace('|', '%7C')
                            processed_data[i['nameEn']][category] = {'id': k['id'], 'url': url}
                else:
                    if j['nameEn'] not in ['-', 'View All']:
                        category = j['nameEn'].lower().replace(' ', '-').replace('|', '&')
                        url = f"{base_url}/{i['nameEn']}/{j['nameEn']}-c{j['id']}.html".lower().replace(' ', '-').replace('|', '%7C')
                        processed_data[i['nameEn']][category] = {'id': j['id'], 'url': url}

        elif i['nameEn'] in ['Teen', 'Kids']:
            for j in i['subcategories']:
                for k in j['subcategories']:
                    subcat = k.get('subcategories')
                    if subcat:
                        for l in k['subcategories']:
                            if l['nameEn'] not in ['-', 'View All']:
                                category = f"{j['nameEn'].lower().replace(' ', '-')}_{k['nameEn'].lower().split(' ')[-1]}_{l['nameEn'].lower().replace(' ', '-').replace('|', '&')}"
                                url = f"{base_url}/{i['nameEn']}/{j['nameEn']}/{k['nameEn']}/{l['nameEn']}-c{l['id']}.html".lower().replace(' ', '-').replace('|', '%7C')
                                processed_data[i['nameEn']][category] = {'id': l['id'], 'url': url}
                    else:
                        if k['nameEn'] not in ['-', 'View All']:
                            category = f"{j['nameEn'].lower().replace(' ', '-')}_{k['nameEn'].lower().replace(' ', '-').replace('|', '&')}"
                            url = f"{base_url}/{i['nameEn']}/{j['nameEn']}/{k['nameEn']}-c{k['id']}.html".lower().replace(' ', '-').replace('|', '%7C')
                            processed_data[i['nameEn']][category] = {'id': k['id'], 'url': url}
                            
    return processed_data

def fetch_and_save_for_country(country, today_date, config, re_run=False):
    """Worker function to fetch, process, and save data for a single country."""
    country_config = config.get(country)
    if not country_config:
        logging.warning(f"No configuration found for {country}. Skipping.")
        return

    output_path = os.path.join(country, today_date, 'Category')
    output_file = os.path.join(output_path, f'{country}_category.json')

    if os.path.exists(output_file) and not re_run:
        logging.info(f"Category file for {country} on {today_date} already exists. Skipping.")
        return

    logging.info(f"Fetching category URLs for {country}...")
    
    raw_data = get_category_ids_from_api(country, country_config['store_id'], country_config)
    if raw_data:
        processed_data = process_category_data(raw_data, country_config['base_url'])
        
        os.makedirs(output_path, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=4)
        
        logging.info(f"Successfully saved category URLs for {country} to {output_file}")

def get_category_urls(countries, today_date, config, re_run=False):
    """
    Fetches category URLs for the specified countries concurrently and saves them to JSON files.
    """
    logging.info("Starting Step 1: Get Category URLs")
    with ThreadPoolExecutor(max_workers=len(countries) or 1) as executor:
        # Use a lambda to pass arguments to the worker function
        executor.map(lambda c: fetch_and_save_for_country(c, today_date, config, re_run), countries)
