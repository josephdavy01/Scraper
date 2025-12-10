import json
import time
import logging
import multiprocessing
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin
import requests
import random
from alert import raise_ticket

# Set up logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ScraperManager:
    def __init__(self, country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, use_api=True, file_lock=None):
        self.country = country
        self.config = CONFIG[country]
        self.today = TODAY_DATE
        self.use_api = use_api
        self.country_code = COUNTRY_CODE_MAP.get(country, 'US')
        self.base_url = COUNTRIES[country]
        self.url_prefix = self._get_url_prefix(country)
        self.USER_AGENTS = USER_AGENTS
        self.file_lock = file_lock

        self.output_dir = Path(f"{self.config['data_dir']}/{self.today}/Item_urls")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results_file = self.output_dir / f"{self.country}_product_links.json"
        self.progress_file = self.output_dir / f"{self.country}_progress.log"

        self.existing_results = self._load_existing_results()
        self.completed_urls = self._load_completed_urls()

        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": random.choice(self.USER_AGENTS)
        })

    def _get_url_prefix(self, country):
        return {
            'USA': 'https://www.aloyoga.com/',
            'UK': 'https://www.aloyoga.com/en-gb/',
            'Canada': 'https://www.aloyoga.com/en-ca/'
        }.get(country, 'https://www.aloyoga.com/')

    def _ensure_country_prefix(self, url):
        if not url:
            return url
        if url.startswith(self.url_prefix):
            return url
        if url.startswith('https://www.aloyoga.com/'):
            return url.replace('https://www.aloyoga.com/', self.url_prefix)
        if url.startswith('/'):
            return urljoin(self.url_prefix, url.lstrip('/'))
        return urljoin(self.url_prefix, url)

    def _load_existing_results(self):
        if self.results_file.exists():
            try:
                with open(self.results_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logging.error(f"[{self.country}] JSON decode error: {e}")
                return {}
        return {}

    def _load_completed_urls(self):
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _save_results(self, gender, category, product_urls):
        if self.file_lock:
            self.file_lock.acquire()
        try:
            current_results = self._load_existing_results()
            if gender not in current_results:
                current_results[gender] = {}
            current_results[gender][category] = product_urls

            with open(self.results_file, 'w') as f:
                json.dump(current_results, f, indent=4)

            with open(self.progress_file, 'a') as f:
                f.write(f"{gender}|{category}\n")
        finally:
            if self.file_lock:
                self.file_lock.release()

    def extract_handle_from_url(self, url):
        return url.split('/collections/')[-1].split('?')[0].split('#')[0]

    def get_total_products_api(self, handle):
        payload = {
            "operationName": "GetCollectionData",
            "variables": {
                "handle": handle,
                "offset": 0,
                "limit": 1,
                "sortKey": "DEFAULT",
                "filters": [],
                "countryCode": self.country_code
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "1647816df62eafdb2ef8305209f54c5c24a715ee12af8e0a86721913abb10dd1"
                }
            }
        }

        try:
            response = self.session.post(
                "https://product-service.alo.software/graphql?opName=GetCollectionData",
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("productsByCollectionHandle", {}).get("products", {}).get("totalCount", 0)
        except Exception as e:
            logging.error(f"[{self.country}] Error fetching product count: {e}")
        return 0

    def extract_product_urls_api(self, handle):
        product_urls = []
        offset = 0
        limit = 15

        while True:
            payload = {
                "operationName": "GetCollectionData",
                "variables": {
                    "handle": handle,
                    "offset": offset,
                    "limit": limit,
                    "sortKey": "DEFAULT",
                    "filters": [],
                    "countryCode": self.country_code
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "1647816df62eafdb2ef8305209f54c5c24a715ee12af8e0a86721913abb10dd1"
                    }
                }
            }

            try:
                response = self.session.post(
                    "https://product-service.alo.software/graphql?opName=GetCollectionData",
                    json=payload,
                    timeout=30
                )
                if response.status_code != 200:
                    logging.error(f"[{self.country}] API failed at offset {offset}")
                    break

                data = response.json()
                nodes = data.get("data", {}).get("productsByCollectionHandle", {}).get("products", {}).get("nodes", [])

                if not nodes:
                    break

                urls = [node.get("onlineStoreUrl") for node in nodes if node.get("onlineStoreUrl")]
                country_urls = [self._ensure_country_prefix(url) for url in urls]
                product_urls.extend(country_urls)

                offset += limit
            except Exception as e:
                logging.error(f"[{self.country}] Error fetching API data: {e}")
                break

        return product_urls

    def process_url(self, page, gender, category, url):
        if f"{gender}|{category}" in self.completed_urls:
            logging.info(f"[{self.country}] Skipping {gender}/{category} (already done)")
            return

        logging.info(f"[{self.country}] Processing {gender}/{category}")

        try:
            if self.use_api:
                handle = self.extract_handle_from_url(url)
                count = self.get_total_products_api(handle)
                if count == 0:
                    logging.warning(f"[{self.country}] No products found for {handle}")
                    return
                links = self.extract_product_urls_api(handle)
            else:
                page.goto(url, wait_until="load", timeout=60000)
                try:
                    page.click('.closeButton__onjV4S', timeout=5000)
                except:
                    pass

                count_element = page.query_selector('p.OneLinkTx')
                count = int(count_element.inner_text().split('of')[-1].strip().split()[0]) if count_element else 0
                pages = (count // 12) + (1 if count % 12 else 0)

                for i in range(pages):
                    try:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)
                        page.click('button[class*="pagination_button"][aria-disabled="false"]', timeout=5000)
                        time.sleep(2)
                    except:
                        break

                links = set()
                for link in page.query_selector_all('a.link.product-tile__image-link'):
                    href = link.get_attribute('href')
                    if href:
                        links.add(urljoin(self.config['base_url'], href))
                links = list(links)

            self._save_results(gender, category, links)
            logging.info(f"[{self.country}] Saved {len(links)} links for {gender}/{category}")

        except Exception as e:
            logging.error(f"[{self.country}] Error processing {url}: {e}")

def worker(country, queue, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, use_api=True, file_lock=None):
    scraper = ScraperManager(country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, use_api, file_lock)

    if not use_api:
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
    else:
        try:
            while True:
                task = queue.get()
                if task is None:
                    break
                gender, category, url = task
                scraper.process_url(None, gender, category, url)
                queue.task_done()
        finally:
            pass

def get_product_urls(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, use_api=True):
    start_time = time.time()
    multiprocessing.freeze_support()

    processes = []
    queues = {}
    file_lock = multiprocessing.Lock()

    for country, config in CONFIG.items():
        with open(f'{country}/{TODAY_DATE}/{country}_category_links.json') as f:
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
                args=(country, queue, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, use_api, file_lock)
            )
            processes.append(process)
            process.start()

        queues[country] = queue

    for process in processes:
        process.join()

    end_time = time.time()
    logging.info(f"Scraping completed in {end_time - start_time:.2f} seconds")
    logging.info(f"Method used: {'API' if use_api else 'Browser'}")


