import json
import time
import logging
import multiprocessing
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin

# Logging config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ScraperManager:
    def __init__(self, country, CONFIG, TODAY_DATE, file_lock):
        self.country = country
        self.config = CONFIG[country]
        self.today = TODAY_DATE
        self.file_lock = file_lock

        self.output_dir = Path(f"{self.config['data_dir']}/{self.today}/Item_urls")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results_file = self.output_dir / f"{self.country}_product_urls.json"
        self.progress_file = self.output_dir / f"{self.country}_progress.log"

        self.existing_results = self._load_existing_results()
        self.completed_urls = self._load_completed_urls()

    def _load_existing_results(self):
        if self.results_file.exists():
            try:
                with open(self.results_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logging.error(f"[{self.country}] JSON decode error: {e}")
                return {}
        return {}

    def _load_completed_urls(self):
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _save_results(self, gender, category, product_urls):
        """Save results incrementally with thread-safe lock."""
        self.file_lock.acquire()
        try:
            current_results = self._load_existing_results()
            if gender not in current_results:
                current_results[gender] = {}
            current_results[gender][category] = product_urls

            with open(self.results_file, 'w', encoding='utf-8') as f:
                json.dump(current_results, f, indent=4)

            with open(self.progress_file, 'a', encoding='utf-8') as f:
                f.write(f"{gender}|{category}\n")
        finally:
            self.file_lock.release()

    def process_url(self, page, gender, category, url):
        """Process a single category URL and save product URLs."""
        if f"{gender}|{category}" in self.completed_urls:
            logging.info(f"[{self.country}] Skipping already processed {gender}/{category}")
            return

        logging.info(f"[{self.country}] Processing {gender}/{category}")
        try:
            page.goto(url, wait_until="load", timeout=60000)

            try:
                page.click('.closeButton__onjV4S', timeout=5000)
                logging.info(f"[{self.country}] Closed popup/modal")
            except:
                pass

            count_element = page.query_selector('p.OneLinkTx')
            if count_element:
                count_text = count_element.inner_text()
                count = int(count_text.split('of')[-1].strip().split()[0])
                pages = (count // 12) + (1 if count % 12 else 0)
                logging.info(f"[{self.country}] Found {count} products, {pages} pages")
            else:
                pages = 1
                logging.warning(f"[{self.country}] Could not find product count, defaulting to 1 page")

            for i in range(pages):
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
                    page.click('button[class*=\"pagination_button\"][aria-disabled=\"false\"]', timeout=5000)
                    logging.info(f"[{self.country}] Clicked 'Load More' button {i+1}/{pages}")
                    time.sleep(2)
                except:
                    break

            links = set()
            product_elements = page.query_selector_all('a.link.product-tile__image-link')
            for link in product_elements:
                href = link.get_attribute('href')
                if href:
                    full_url = urljoin(self.config['base_url'], href)
                    links.add(full_url)

            self._save_results(gender, category, list(links))
            logging.info(f"[{self.country}] Saved {len(links)} products for {gender}/{category}")
        except Exception as e:
            logging.error(f"[{self.country}] Error processing {url}: {str(e)}")

def worker(country, queue, CONFIG, TODAY_DATE, file_lock):
    """Worker process for a specific country."""
    scraper = ScraperManager(country, CONFIG, TODAY_DATE, file_lock)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            while True:
                task = queue.get()
                if task is None:
                    break
                gender, category, url = task
                scraper.process_url(page, gender, category, url)
                queue.task_done()
        finally:
            context.close()
            browser.close()

def get_product_urls(CONFIG, TODAY_DATE):
    """Main controller for all country scrapers."""
    start_time = time.time()
    multiprocessing.freeze_support()

    processes = []
    file_lock = multiprocessing.Lock()

    for country, config in CONFIG.items():
        with open(f'{country}/{TODAY_DATE}/{country}_category_urls.json', 'r', encoding='utf-8') as f:
            url_dict = json.load(f)

        queue = multiprocessing.JoinableQueue()
        for gender, categories in url_dict.items():
            for category, url in categories.items():
                queue.put((gender, category, url))

        for _ in range(config['browsers']):
            queue.put(None)

        for _ in range(config['browsers']):
            process = multiprocessing.Process(
                target=worker,
                args=(country, queue, CONFIG, TODAY_DATE, file_lock)
            )
            processes.append(process)
            process.start()

    for process in processes:
        process.join()

    end_time = time.time()
    logging.info(f"Scraping completed in {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
# TODAY_DATE = "2025-11-18"
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
    get_product_urls(CONFIG, TODAY_DATE)
