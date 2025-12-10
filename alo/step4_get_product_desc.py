import json
import logging
import multiprocessing
from multiprocessing import JoinableQueue
from pathlib import Path
from playwright.sync_api import sync_playwright
import time
import random

# Set up logging to be consistent with other steps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s'
)

class DescriptionScraper:
    """
    Manages fetching product descriptions and updating JSON files,
    mirroring the structure of ProductScraper in step4.
    """
    def __init__(self, country, config, today_date):
        self.country = country
        self.config = config
        self.today = today_date
        
        # Construct the base URL for the .js files from the config
        lang_path = self.config.get('lang_code', '')
        base_url = 'https://www.aloyoga.com'
        self.products_url = f"{base_url}/{lang_path}/products" if lang_path else f"{base_url}/products"
        
        # Progress tracking
        self.json_data_dir = Path(self.config['data_dir']) / self.today / "Json_data"
        self.progress_file = self.json_data_dir / f"{self.country}_description_progress.log"
        self.completed_files = self._load_completed_files()

    def _load_completed_files(self):
        """Loads the set of file paths that have already been processed."""
        if self.progress_file.exists():
            with self.progress_file.open('r') as f:
                return set(line.strip() for line in f)
        return set()

    def _mark_as_completed(self, file_path):
        """Marks a file as completed by appending its path to the progress log."""
        # This operation should be atomic if multiple processes write, but for one file per process, it's fine.
        with self.progress_file.open('a') as f:
            f.write(f"{file_path}\n")

    def get_files_to_process(self):
        """Returns a list of all JSON files that have not yet been processed."""
        if not self.json_data_dir.exists():
            logging.warning(f"[{self.country}] JSON data directory not found: {self.json_data_dir}")
            return []
            
        all_files = [p for p in self.json_data_dir.rglob("*.json") if p.is_file()]
        
        return [
            file for file in all_files 
            if str(file.resolve()) not in self.completed_files
        ]

    def fetch_description_with_browser(self, page, file_path):
        """
        The core logic: uses the provided Playwright page to fetch the description.
        """
        try:
            with file_path.open('r', encoding='utf-8') as f:
                data = json.load(f)

            product_handle = data.get("data", {}).get("products", {}).get("edges", [{}])[0].get("node", {}).get("handle")
            if not product_handle:
                logging.warning(f"[{self.country}] No product handle in {file_path.name}, skipping.")
                return

            description_url = f"{self.products_url}/{product_handle}.js"
            
            response = page.goto(description_url, timeout=30000)
            
            if response.status == 200:
                description_data = response.json()
                description = description_data.get('description')
                if description:
                    data['description'] = description
                    with file_path.open('w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4)
                    self._mark_as_completed(str(file_path.resolve()))
                    logging.info(f"[{self.country}] Success for {file_path.name}")
                else:
                    logging.warning(f"[{self.country}] No description content found at {description_url}")
            else:
                logging.error(f"[{self.country}] Failed to fetch {description_url} | Status: {response.status}")

        except Exception as e:
            logging.error(f"[{self.country}] Critical error processing {file_path.name}: {e}", exc_info=True)


def worker_descriptions(country, queue, config, today_date, browser_id):
    """
    Worker function that mirrors `worker_browser_multiple` from step4.
    Each worker initializes its own browser instance.
    """
    process_name = f"{country}-DescWorker-{browser_id}"
    multiprocessing.current_process().name = process_name
    
    scraper = DescriptionScraper(country, config, today_date)
    
    with sync_playwright() as playwright:
        browser = None
        try:
            browser = playwright.chromium.launch(headless=False) # Set to True for production
            context = browser.new_context()
            page = context.new_page()
            logging.info(f"Browser {browser_id} for {country} initialized.")
            
            while True:
                task = queue.get()
                if task is None:
                    logging.info(f"Sentinel received. Exiting worker {browser_id} for {country}.")
                    break
                
                file_path = Path(task)
                scraper.fetch_description_with_browser(page, file_path)
                time.sleep(random.uniform(1, 3)) # Optional delay
                queue.task_done()
                    
        except Exception as e:
            logging.error(f"Worker {browser_id} for {country} encountered a fatal error: {e}", exc_info=True)
        finally:
            if browser:
                browser.close()
            logging.info(f"Browser {browser_id} for {country} closed.")


def get_product_descriptions(CONFIG, TODAY_DATE, re_run=False):
    """
    Main entry point that mirrors the setup from `process_mode_fast` in step4.
    """
    multiprocessing.freeze_support()
    processes = []
    
    if re_run:
        # Clear progress files if re-running
        for country, config in CONFIG.items():
            progress_file = Path(config['data_dir']) / TODAY_DATE / "Json_data" / f"{country}_description_progress.log"
            if progress_file.exists():
                progress_file.unlink()
                logging.info(f"Cleared description progress file for {country}")

    for country, config in CONFIG.items():
        # Instantiate scraper just to get the list of files for this country
        scraper = DescriptionScraper(country, config, TODAY_DATE)
        files_to_process = scraper.get_files_to_process()

        if not files_to_process:
            logging.info(f"[{country}] No new product descriptions to fetch. Skipping.")
            continue
        
        logging.info(f"[{country}] Found {len(files_to_process)} products missing descriptions.")

        queue = JoinableQueue()
        for file_path in files_to_process:
            queue.put(str(file_path.resolve()))
        
        # Add a sentinel value for each browser/worker process
        for _ in range(config['browsers']):
            queue.put(None)
        
        # Launch worker processes, mirroring step4
        for i in range(config['browsers']):
            process = multiprocessing.Process(
                target=worker_descriptions,
                args=(country, queue, config, TODAY_DATE, i + 1)
            )
            processes.append(process)
            process.start()
    
    for process in processes:
        process.join()
    
    logging.info("All product description scraping tasks are complete.")