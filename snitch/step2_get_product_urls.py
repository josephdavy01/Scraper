import json
import logging
import os
import multiprocessing
from pathlib import Path
from datetime import date, datetime
from urllib.parse import quote
from alert import raise_ticket
from curl_cffi import requests

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class ProductUrlScraper:
    def __init__(self, country, config, today_date):
        self.country = country
        self.config = config
        self.today_date = today_date
        self.base_url = config.get('base_url')
        self.data_dir = Path(f"{country}/{today_date}/Item_urls")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.data_dir / f"{country}_product_links.json"
        self.headless = config.get('headless', False)
        
        # Log files for tracking progress
        self.success_log = self.data_dir / "success_url.log"
        self.fail_log = self.data_dir / "fail_url.log"
        
        # Load already processed categories
        self.processed_categories = self._load_processed_categories()

    def _load_processed_categories(self):
        """Load list of successfully processed categories from success log."""
        processed = set()
        if self.success_log.exists():
            try:
                with open(self.success_log, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            # Format: timestamp|gender|category|url_count
                            parts = line.split('|')
                            if len(parts) >= 3:
                                gender, category = parts[1], parts[2]
                                processed.add(f"{gender}||{category}")
            except Exception as e:
                logging.warning(f"Error reading success log: {e}")
        return processed
    
    def _is_already_processed(self, gender, category):
        """Check if a category was already successfully processed."""
        key = f"{gender}||{category}"
        return key in self.processed_categories
    
    def _log_success(self, gender, category, url_count):
        """Log successful processing to success_url.log."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"{timestamp}|{gender}|{category}|{url_count}\n"
            with open(self.success_log, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            logging.info(f"[{self.country}] Logged success for {gender} > {category}")
        except Exception as e:
            logging.error(f"Error writing to success log: {e}")
    
    def _log_failure(self, gender, category, error_msg):
        """Log failed processing to fail_url.log."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"{timestamp}|{gender}|{category}|{error_msg}\n"
            with open(self.fail_log, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            logging.error(f"[{self.country}] Logged failure for {gender} > {category}")
        except Exception as e:
            logging.error(f"Error writing to fail log: {e}")

    def _save_data(self, gender, category, new_urls):
        """Saves data to JSON file safely."""
        if not new_urls:
            return

        try:
            # Read existing data
            if os.path.exists(self.results_file):
                with open(self.results_file, 'r', encoding='utf-8') as f:
                    try:
                        full_data = json.load(f)
                    except json.JSONDecodeError:
                        full_data = {}
            else:
                full_data = {}

            if gender not in full_data:
                full_data[gender] = {}
            
            existing = set(full_data[gender].get(category, []))
            updated = existing.union(new_urls)
            full_data[gender][category] = list(updated)

            # Write back
            with open(self.results_file, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=4, ensure_ascii=False)
            
            logging.info(f"[{self.country}] Saved {len(new_urls)} new URLs for {gender} > {category}")

        except Exception as e:
            logging.error(f"[{self.country}] Save Error: {e}")

    def get_urls(self, category, base_url):
        """Fetch product URLs using curl_cffi instead of Playwright"""
        
        seen_urls = set()   
        page_number = 1

        while True:
            # properly encode the category for the URL
            encoded_category = quote(category)
            api_url = f"https://mxemjhp3rt.ap-south-1.awsapprunner.com/products/plp/v2?page={page_number}&limit=50&0=%5Bobject+Object%5D&product_type={encoded_category}"
            
            try:
                # Use curl_cffi to make the request
                response = requests.get(api_url, impersonate="chrome120", timeout=30)
                
                # --- LOGIC FIX: Handle End of Pagination vs Actual Errors ---
                if response.status_code != 200:
                    if page_number > 1 and response.status_code in [400, 404]:
                        # This is normal. We reached the end of the pages.
                        logging.info(f"[{self.country}] Reached end of pagination for {category} at page {page_number}")
                        break
                    else:
                        # This is an actual error (e.g., Page 1 fails, or 500 server error)
                        error_msg = f"API returned status {response.status_code} for {category} page {page_number}"
                        logging.warning(error_msg)
                        raise Exception(error_msg) # Raise so run() logs it as failure
                
                try:
                    json_data = response.json()
                except Exception as e:
                    error_msg = f"Invalid JSON response on page {page_number} for {category}: {e}"
                    logging.error(error_msg)
                    raise Exception(error_msg) # Raise so run() logs it as failure

                products = json_data.get('data', {}).get('products', [])

                if not products:
                    logging.info(f"No more products found on page {page_number} for {category}")
                    break

                for product in products:
                    handle = product.get('handle')
                    product_id = product.get('shopify_product_id')
                    if handle and product_id:
                        # Ensure we are replacing 'buy' in the URL provided by the worker (not base_url)
                        if 'buy' in base_url:
                            product_link = base_url.replace('buy', f'{handle}/{str(product_id)}/buy')
                        else:
                            # Fallback if the URL doesn't have 'buy' (prevents the previous bug)
                            product_link = f"https://www.snitch.com/{handle}/{str(product_id)}/buy"
                            
                        if product_link not in seen_urls:
                            seen_urls.add(product_link)
                            yield product_link 
                
                page_number += 1
                
            except Exception as e:
                logging.error(f"Error scraping page {page_number} for {category}: {e}")
                raise e # Re-raise the exception so run() knows it failed

    def run(self, gender, category, url):
        # Check if already processed
        if self._is_already_processed(gender, category):
            logging.info(f"[{self.country}] Skipping {gender} > {category} (already processed)")
            return
        
        logging.info(f"[{self.country}] Scraping {gender} > {category}")
        
        new_urls = set()
        try:
            for product_url in self.get_urls(category, url):
                new_urls.add(product_url)
            
            # Save data if URLs were found
            if new_urls:
                self._save_data(gender, category, new_urls)
                # Log success
                self._log_success(gender, category, len(new_urls))
            else:
                logging.warning(f"[{self.country}] No URLs found for {category}")
                # Still log as success (empty category is valid)
                self._log_success(gender, category, 0)
                
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error in run loop for {category}: {error_msg}")
            # Log failure
            self._log_failure(gender, category, error_msg)
            raise_ticket("Step 2", "run", f"Scraping failed for {category}: {error_msg}", self.country)
            raise  # Re-raise to let worker handle it


# --- Worker Function ---
def worker(task_queue, country, config, today_date):
    scraper = ProductUrlScraper(country, config, today_date)
    while True:
        task = task_queue.get()
        if task is None:
            task_queue.task_done()
            break
        
        gender, category, url = task
        try:
            scraper.run(gender, category, url)
        except Exception as e:
            logging.error(f"Worker Error: {e}")
        finally:
            task_queue.task_done()


# Main script
def get_product_urls(config_dict, today_date, user_agents, countries, country_code_map, use_api=False):
    """
    Main function to get product URLs.
    Matches arguments passed from master.py.
    """
    logging.info("--- Starting Product URL Extraction ---")
    
    processes = []
    
    # Iterate over the countries passed in (COUNTRIES_TUE_THU_SAT)
    for country, url in countries.items():
        # Get specific config for this country
        country_config = config_dict.get(country, {})
        if not country_config:
            logging.warning(f"No config found for {country}, skipping.")
            continue

        # Input file from Step 1
        input_file = f'{country}/{today_date}/Category/{country}_category_urls.json'
        
        if not os.path.exists(input_file):
            logging.warning(f"Missing category file: {input_file}")
            raise_ticket("Step 2", "get_product_urls", f"Missing category file for {country}", country)
            continue
            
        with open(input_file, 'r', encoding='utf-8') as f:
            cat_data = json.load(f)
            
        queue = multiprocessing.JoinableQueue()
        
        # Populate Queue
        for gender, subcats in cat_data.items():
            for subcat, val in subcats.items():
                if isinstance(val, str) and val.startswith('http'):
                    queue.put((gender, subcat, val))
        
        # Start Workers
        num_browsers = country_config.get('browsers', 1)
        for _ in range(num_browsers):
            queue.put(None) # Sentinel
            p = multiprocessing.Process(target=worker, args=(queue, country, country_config, today_date))
            p.start()
            processes.append(p)
            
    for p in processes:
        p.join()
        
    logging.info("All Product URL tasks finished.")
