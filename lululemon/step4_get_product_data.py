import json
import time
import logging
import multiprocessing
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from multiprocessing import Queue, Lock

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ProductScraper:
    def __init__(self, country, CONFIG, TODAY_DATE):
        self.country = country
        self.config = CONFIG[country]
        self.today = TODAY_DATE
        self.output_dir = Path(f"{self.config['data_dir']}/{self.today}")
        self.progress_file = self.output_dir / f"{self.country}_product_progress.log"
        
        # Load completed URLs
        self.completed_urls = self._load_completed_urls()
        
    def _load_completed_urls(self):
        """Load already processed URLs from progress file"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _save_product_data(self, gender, category, product_id, product_data, url):
        """Save product data to JSON file"""
        try:
            output_path = self.output_dir / 'Json_data' / gender / category
            output_path.mkdir(parents=True, exist_ok=True)
            
            with open(output_path / f"{product_id}.json", 'w') as f:
                json.dump(product_data, f, indent=4)
            
            # Update progress log with full URL
            with Lock():  # Ensure thread-safe file operations
                with open(self.progress_file, 'a') as f:
                    f.write(f"{url}\n")  # Log the full URL instead of product details
                
        except Exception as e:
            logging.error(f"[{self.country}] Error saving {product_id}: {e}")

    def scrape_product(self, page, gender, category, url):
        """Scrape a single product page"""
        try:
            # Check if URL has already been processed
            if url in self.completed_urls:
                logging.info(f"[{self.country}] Skipping already processed URL: {url}")
                return
            
            product_id = url.split('/_/')[0].split('/')[-1]
            logging.info(f"[{self.country}] Processing {gender}/{category}/{product_id} - {url}")
            
            # Navigate to product page
            page.goto(url, wait_until="load", timeout=30000)
            
            # Extract product data
            script_content = page.evaluate("document.getElementById('__NEXT_DATA__')?.textContent")
            if not script_content:
                raise Exception("Could not find __NEXT_DATA__ script")

            json_data = json.loads(script_content)
            product = json_data['props']['pageProps']['initialStoreState']['productDetailPage']['current']
            
            # Save the data
            self._save_product_data(gender, category, product_id, product, url)
            logging.info(f"[{self.country}] Saved {gender}/{category}/{product_id}")
            
        except Exception as e:
            logging.error(f"[{self.country}] Error processing {url}: {e}")

def worker(country, queue, CONFIG, TODAY_DATE):
    """Worker process that handles URLs from the queue"""
    scraper = ProductScraper(country, CONFIG, TODAY_DATE)
    
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            while True:
                task = queue.get()
                if task is None:  # Sentinel value to stop
                    break

                gender, category, url = task
                scraper.scrape_product(page, gender, category, url)
                queue.task_done()

        finally:
            context.close()
            browser.close()

def get_product_data(CONFIG, TODAY_DATE):
    """Main function to coordinate scraping for all countries"""
    multiprocessing.freeze_support()
    processes = []
    queues = {}

    # Create queues and add tasks for each country
    for country, config in CONFIG.items():
        # Load product URLs
        url_file = Path(f"{country}/{TODAY_DATE}/Item_urls/{country}_product_urls.json")
        
        with open(url_file) as f:
            urls_dict = json.load(f)

        # Create queue and add tasks
        queue = multiprocessing.JoinableQueue()
        for gender, categories in urls_dict.items():
            for category, urls in categories.items():
                for url in urls:
                    queue.put((gender, category, url))

        # Add sentinel values for each worker
        for _ in range(config['browsers']):
            queue.put(None)

        # Start worker processes
        for _ in range(config['browsers']):
            process = multiprocessing.Process(
                target=worker,
                args=(country, queue, CONFIG, TODAY_DATE)
            )
            processes.append(process)
            process.start()

        queues[country] = queue

    # Wait for all processes to complete
    for process in processes:
        process.join()

    logging.info("All product scraping tasks completed")

if __name__ == "__main__":
    TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
    TODAY_DATE = "2025-12-09"
    TODAY_DATE_OBJ = datetime.strptime(TODAY_DATE, "%Y-%m-%d")
    TODAY = TODAY_DATE_OBJ.strftime("%A")

    COUNTRIES = {
        'Canada': 'https://shop.lululemon.com/en-ca/',
        'USA': 'https://shop.lululemon.com/'
    }

    # Configuration
    CONFIG = {
        'USA': {
            'base_url': 'https://shop.lululemon.com',
            'browsers': 2,
            'data_dir': 'USA'
        },
        'Canada': {
            'base_url': 'https://shop.lululemon.com/en-ca',
            'browsers': 2,
            'data_dir': 'Canada'
        }
    }
    get_product_data(CONFIG, TODAY_DATE)

