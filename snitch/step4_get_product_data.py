import json
import time
import logging
import os
from pathlib import Path
from datetime import date, datetime
from curl_cffi import requests
from alert import raise_ticket

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ProductDataScraper:
    def __init__(self, country, config, today_date):
        self.country = country
        self.config = config
        self.today_date = today_date
        self.base_url = config.get('base_url')
        self.max_retries = config.get('max_retries', 3)
        self.timeout = config.get('timeout', 15)  # Timeout in seconds
        
        # File Setup
        self.data_dir = f"{country}/{today_date}/Json_data"
        self.success_log = f"{country}/{today_date}/Validation/success_log.txt"
        self.failed_log = f"{country}/{today_date}/Validation/failed_log.txt"
        
        os.makedirs(self.data_dir, exist_ok=True)

    def log_success(self, url):
        with open(self.success_log, 'a', encoding='utf-8') as f:
            f.write(f"{url}\n")

    def log_failure(self, url, reason):
        with open(self.failed_log, 'a', encoding='utf-8') as f:
            f.write(f"{url} | Error: {reason}\n")
        # Only raise ticket if failure is critical or persistent? 
        # For now, logging to file is enough, master.py checks deviation.
        # If we want per-product failure tickets, uncomment below, but it might be spammy.
        # raise_ticket("Step 4", "log_failure", f"Failed to extract {url}", self.country)

    def save_json(self, gender, category, name, json_data):
        try:
            json_file_path = f'{self.data_dir}/{gender}/{category}'
            os.makedirs(json_file_path, exist_ok=True)
            with open(f'{json_file_path}/{name}.json', 'w', encoding='utf-8') as outfile:
                json.dump(json_data, outfile, indent=4, ensure_ascii=False)
            logging.info(f"[{self.country}] Saved {name}.json")
            return True
        except Exception as e:
            logging.error(f"[{self.country}] Error saving JSON file for product {name}: {e}")
            return False

    def check_file(self, gender, category, name):
        return os.path.exists(f'{self.data_dir}/{gender}/{category}/{name}.json')

    def fetch_json_data(self, url):
        """Fetch JSON data from URL using curl_cffi with chrome120 impersonation"""
        try:
            response = requests.get(url, impersonate="chrome120", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to fetch data from {url}: {e}")

    def process_urls(self, gender, category, urls):
        for url in urls:
            try:
                id = url.split('/')[-2]
                name = url.split('/')[-3]
                
                if self.check_file(gender, category, name):
                    continue

                success = False
                for attempt in range(self.max_retries):
                    try:
                        purl = f'https://mxemjhp3rt.ap-south-1.awsapprunner.com/products/product-details?product_id={id}'
                        surl = f'https://mxemjhp3rt.ap-south-1.awsapprunner.com/products/size-info/v2?product_id={id}'

                        # Fetch product details API using curl_cffi
                        product_json = self.fetch_json_data(purl)

                        # Fetch size info API using curl_cffi
                        size_json = self.fetch_json_data(surl)

                        product = {
                            'product': product_json.get('data', {}).get('products'),
                            'sizes': size_json.get('data')
                        }

                        if product['product']:
                            if self.save_json(gender, category, name, product):
                                self.log_success(url)
                                yield name
                                success = True
                                break
                    except Exception as e:
                        logging.warning(f"Attempt {attempt+1}/{self.max_retries} failed for {url}: {e}")
                        time.sleep(2) # Wait before retry

                if not success:
                    self.log_failure(url, "Max retries reached")

            except Exception as e:
                logging.error(f"Error processing URL {url}: {e}")
                self.log_failure(url, str(e))

def get_product_data(config_dict, today_date, user_agents, countries, country_code_map, re_run=False):
    for country, config in config_dict.items():
        scraper = ProductDataScraper(country, config, today_date)
        input_file = f'{country}/{today_date}/Item_urls/{country}_product_links.json'
        
        if not os.path.exists(input_file):
            logging.warning(f"Missing product links file: {input_file}")
            raise_ticket("Step 4", "get_product_data", f"Missing product links file for {country}", country)
            continue

        with open(input_file, 'r', encoding='utf-8') as f:
            urls_dict = json.load(f)

        for gender, categories in urls_dict.items():
            for category, urls in categories.items():
                # Check if we need to run this category
                if re_run or not all(scraper.check_file(gender, category, url.split('/')[-3]) for url in urls):
                    logging.info(f'Starting {country} {gender} {category} section...')
                    for product_name in scraper.process_urls(gender, category, urls):
                        logging.info(f'Processed product: {product_name}')
                    logging.info(f'{country} {gender} {category} section complete.')
                else:
                    logging.info(f"[{country}] Data for {gender} > {category} already exists. Skipping...")

if __name__ == "__main__":
    # Example config to run standalone
    config = {
        "India": {
            "base_url": "https://www.snitch.co.in/",
            "timeout": 15
        }
    }
    today = date.today().strftime('%Y-%m-%d')
    # Dummy args for standalone run
    get_product_data(config, today, [], {"India": ""}, {}, False)