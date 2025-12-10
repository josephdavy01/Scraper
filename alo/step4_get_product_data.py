import json
import time
import logging
import multiprocessing
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from multiprocessing import Queue
import aiohttp
import random
import os
import threading

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- ROBUST FILE LOCKING CLASS ---
class FileLock:
    """A file locking mechanism that works across processes and handles crashes"""
    def __init__(self, filename):
        self.lockfile = f"{filename}.lock"
        self.timeout = 20  # Seconds to wait for lock before assuming stale/crash

    def acquire(self):
        start_time = time.time()
        while True:
            try:
                # Atomic exclusive creation - this fails if file exists
                fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.close(fd)
                return True
            except OSError:
                # Check for STALE lock (older than 20 seconds)
                try:
                    if os.path.exists(self.lockfile):
                        if time.time() - os.path.getmtime(self.lockfile) > self.timeout:
                            logging.warning(f"Removing stale lock file: {self.lockfile}")
                            os.remove(self.lockfile)
                            continue 
                except OSError:
                    pass 

                if time.time() - start_time > self.timeout:
                    logging.warning(f"Timeout waiting for lock: {self.lockfile}")
                    return False 
                time.sleep(0.1)

    def release(self):
        try:
            if os.path.exists(self.lockfile):
                os.remove(self.lockfile)
        except OSError:
            pass 

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

class ProductScraper:
    def __init__(self, country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, mode='api'):
        self.country = country
        self.config = CONFIG[country]
        self.today = TODAY_DATE
        self.mode = mode  # 'api', 'sale_api', or 'normal'
        self.country_code = COUNTRY_CODE_MAP.get(country, 'US')
        self.base_url = COUNTRIES[country]
        self.USER_AGENTS = USER_AGENTS
        self.country_full_name = COUNTRY_MAPPING.get(country, country)
        
        # Single output directory for all modes
        self.output_dir = Path(f"{self.config['data_dir']}/{self.today}/Json_data")
        self.progress_file = self.output_dir / f"{self.country}_product_progress_{mode}.log"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Global progress tracker - tracks ALL modes
        self.global_progress_file = self.output_dir / f"{self.country}_global_progress.json"
        
        # Initialize FileLock based on the global progress file path
        self.file_lock = FileLock(str(self.global_progress_file))
        
        # Initial load of completed URLs for this specific mode (from .log file)
        self.completed_urls = self._load_completed_urls()
        
        # aiohttp session for API calls
        self.session = None

    def _load_completed_urls(self):
        """Load already processed URLs for this specific mode from .log"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _read_json_safely(self):
        """Helper to read JSON content safely inside a lock"""
        if self.global_progress_file.exists():
            try:
                with open(self.global_progress_file, 'r') as f:
                    content = f.read()
                    if content:
                        return json.loads(content)
            except (json.JSONDecodeError, ValueError):
                pass
        return {
            "api": [], "sale_api": [], "normal": [],
            "successfully_processed": [], "failed_processed": []
        }

    def _save_global_progress(self, url, success=True):
        """Save global progress with STRICT SELF-HEALING LOGIC"""
        with self.file_lock:
            # 1. Re-load data from disk to get the absolute latest state
            data = self._read_json_safely()

            # Convert lists to sets for easy logic operations
            success_set = set(data.get("successfully_processed", []))
            failed_set = set(data.get("failed_processed", []))
            mode_set = set(data.get(self.mode, []))

            # 2. Record that we ATTEMPTED this URL in the current mode
            mode_set.add(url)
            data[self.mode] = list(mode_set)

            # 3. Handle Success/Failure Logic
            if success:
                success_set.add(url)
            else:
                # Only add to failed if it has NEVER been successful
                if url not in success_set:
                    failed_set.add(url)

            # 4. CRITICAL FIX: SELF-HEALING
            # Mathematically ensure no URL in 'success' exists in 'failed'
            failed_set = failed_set - success_set

            # 5. Write back to disk
            data["successfully_processed"] = list(success_set)
            data["failed_processed"] = list(failed_set)
            
            with open(self.global_progress_file, 'w') as f:
                json.dump(data, f, indent=2)

    def _should_process_url(self, url):
        """Determine if URL should be processed based on GLOBAL state"""
        # 1. Fast check: has this specific mode already done it?
        if url in self.completed_urls:
            return False

        # 2. Strict check: has ANY mode successfully scraped it?
        # We safely check the file to ensure we have fresh data from other workers
        with self.file_lock:
            data = self._read_json_safely()
            success_set = set(data.get("successfully_processed", []))
            
            if url in success_set:
                return False
            
            # If not successful yet, we should process it
            return True

    def _save_product_data(self, gender, category, product_id, product_data, url):
        """Save product data and update progress"""
        try:
            output_path = self.output_dir / gender.upper() / category
            output_path.mkdir(parents=True, exist_ok=True)
            
            product_file = output_path / f"{product_id}.json"
            with open(product_file, 'w') as f:
                json.dump(product_data, f, indent=4)
            
            try:
                with open(self.progress_file, 'a') as f:
                    f.write(f"{url}\n")
            except:
                pass
            
            # Update global progress (Cleanly removes from failed list)
            self._save_global_progress(url, success=True)
            
        except Exception as e:
            logging.error(f"[{self.country}] Error saving {product_id}: {e}")
            self._save_global_progress(url, success=False)

    @staticmethod
    def extract_style_id(url):
        slug = url.rstrip('/').split('/')[-1]
        return slug.split('-')[0]

    # --- API Mode Methods ---
    async def init_session(self):
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": random.choice(self.USER_AGENTS)
                }
            )

    async def close_session(self):
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                logging.error(f"Error closing session: {e}")
            self.session = None

    async def fetch_product_data_api(self, style_id, is_sale=False):
        await self.init_session()
        
        if is_sale:
            query = f"tag:'StyleId:{style_id}' tag:'pricing:saleprice'"
        else:
            query = f"tag:'StyleId:{style_id}' tag:'pricing:fullprice'"
        
        payload = {
            "operationName": "colorwayProducts",
            "variables": {
                "productSearchQuery": query,
                "countryCode": self.country_code
            },
            "query": """
                query colorwayProducts($productSearchQuery: String!, $countryCode: CountryCode) @inContext(country: $countryCode) {
                  products(first: 80, query: $productSearchQuery) {
                    edges {
                      node {
                        ...PdpProductDetails
                        __typename
                      }
                      __typename
                    }
                    __typename
                  }
                }
                fragment PdpProductDetails on Product {
                  id
                  title
                  productType
                  onlineStoreUrl
                  tags
                  vendor
                  availableColors: metafield(namespace: \"alo-swatch\", key: \"available-colors\") {
                    value
                    __typename
                  }
                  media(first: 250) {
                    edges {
                      node {
                        ... on Video {
                          id
                          sources {
                            width
                            height
                            url
                            mimeType
                            format
                            __typename
                          }
                          previewImage {
                            id
                            transformedSrc
                            __typename
                          }
                          __typename
                        }
                        __typename
                      }
                      __typename
                    }
                    __typename
                  }
                  attributes: metafields(identifiers: [
                    {namespace: \"attribs\", key: \"fit\"},
                    {namespace: \"attribs\", key: \"fabrication\"},
                    {namespace: \"attribs\", key: \"whyWeLoveIt\"},
                    {namespace: \"attribs\", key: \"howToUse\"},
                    {namespace: \"attribs\", key: \"tested & Approved\"},
                    {namespace: \"attribs\", key: \"quickFit\"},
                    {namespace: \"attribs\", key: \"quickFitSizeSelector\"},
                    {namespace: \"attribs\", key: \"getTheLook\"}]) {
                    key
                    value
                    __typename
                  }
                  images(first: 25) {
                    edges {
                      node {
                        url: transformedSrc(maxWidth: 750)
                        __typename
                      }
                      __typename
                    }
                    __typename
                  }
                  variants(first: 50) {
                    edges {
                      node {
                        id
                        sku
                        selectedOptions {
                          name
                          value
                          __typename
                        }
                        image {
                          url: transformedSrc(maxWidth: 750)
                          __typename
                        }
                        priceV2 {
                          amount
                          __typename
                        }
                        compareAtPriceV2 {
                          amount
                          __typename
                        }
                        requiresShipping
                        availableForSale
                        quantityAvailable
                        estimatedShipStartDate: metafield(namespace: \"preorder\", key: \"estimated_ship_date\") {
                          value
                          __typename
                        }
                        __typename
                      }
                      __typename
                    }
                    __typename
                  }
                  availableForSale
                  handle
                  totalInventory
                  __typename
                }
            """
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Storefront-Access-Token": "d7ef45a4f583a78079bfebcb868b5931"
        }
        
        for attempt in range(3):
            try:
                async with self.session.post(
                    "https://alo-yoga.myshopify.com/api/2025-01/graphql.json?opName=colorwayProducts",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logging.error(f"API error {response.status} for {style_id}")
            except Exception as e:
                logging.error(f"[Attempt {attempt+1}] Network error for {style_id}: {e}")
                await asyncio.sleep(2 + attempt * 2)
        
        return None

    async def process_url_api(self, gender, category, url):
        try:
            if not self._should_process_url(url):
                return

            product_id = url.split('/_/')[0].split('/')[-1]
            style_id = self.extract_style_id(url)
            is_sale = (self.mode == 'sale_api')
            
            data = await self.fetch_product_data_api(style_id, is_sale)
            edges = data.get("data", {}).get("products", {}).get("edges") if data else None
            
            if edges:
                self._save_product_data(gender, category, product_id, data, url)
                logging.info(f"[{self.country}] {self.mode.upper()} - Saved {gender}/{category}/{product_id}")
            else:
                logging.warning(f"[{self.country}] {self.mode.upper()} - No product data for: {url}")
                self._save_global_progress(url, success=False)
                
        except Exception as e:
            logging.error(f"[{self.country}] Error processing {url}: {e}")
            self._save_global_progress(url, success=False)

    async def run_concurrent_api(self, url_tasks):
        start_time = time.time()
        new_tasks = []
        
        # Filter URLs that actually need processing
        for g, c, u in url_tasks:
            if self._should_process_url(u):
                new_tasks.append((g, c, u))
        
        if not new_tasks:
            logging.info(f"[{self.country}] No URLs to process for {self.mode.upper()} - all already handled")
            return
        
        logging.info(f"[{self.country}] {self.mode.upper()} - Processing {len(new_tasks)} URLs")
        
        await asyncio.gather(*(self.process_url_api(gender, category, url) for gender, category, url in new_tasks))
        
        duration = time.time() - start_time
        logging.info(f"[{self.country}] {self.mode.upper()} completed in {duration:.2f} seconds")
        
        await self.close_session()

    # --- Normal Mode Methods ---
    def handle_popups(self, page):
        try:
            osano_btn = page.query_selector("button.osano-cm-dialog__close")
            if osano_btn and osano_btn.is_visible():
                osano_btn.click()
        except:
            pass

        try:
            close_btn = page.query_selector("#closeIconContainer")
            if close_btn and close_btn.is_visible():
                close_btn.click()
        except:
            pass

        try:
            for frame in page.frames:
                try:
                    btn = frame.query_selector("#closeIconContainer")
                    if btn and btn.is_visible():
                        btn.click()
                        return True
                except:
                    continue
        except:
            pass
        return False

    def select_country_manually(self, page):
        for attempt in range(3):
            try:
                self.handle_popups(page)
                page.click('div[react-render-target="currency-selector"] button.sc-modal-trigger', timeout=5000)
                time.sleep(1)
                
                input_field = page.wait_for_selector('input.MuiInputBase-input', state="visible", timeout=5000)
                input_field.click()
                input_field.fill(self.country_full_name)
                time.sleep(1)
                
                page.keyboard.press('ArrowDown')
                time.sleep(0.5)
                page.keyboard.press('Enter')
                time.sleep(1)
                
                save_button = page.wait_for_selector('div.sc-modal-buttons button.button-primary', timeout=5000)
                save_button.click()
                time.sleep(2)
                
                logging.info(f"[{self.country}] Country selected successfully")
                return True
            except Exception as e:
                logging.warning(f"[{self.country}] Country selection attempt {attempt + 1} failed: {e}")
                time.sleep(2)
        return False

    def initialize_browser_with_country(self, page):
        try:
            page.goto(self.base_url, timeout=30000, wait_until='domcontentloaded')
            time.sleep(5)
            self.handle_popups(page)
            
            if not page.url.startswith(self.base_url) or self.country == 'USA':
                success = self.select_country_manually(page)
                if not success:
                    logging.error(f"[{self.country}] Failed to select country")
                    return False
                time.sleep(5)
                self.handle_popups(page)
                
                if not page.url.startswith(self.base_url):
                    logging.error(f"[{self.country}] Redirect failed")
                    return False
            
            logging.info(f"[{self.country}] Browser initialized successfully")
            return True
        except Exception as e:
            logging.error(f"[{self.country}] Browser initialization failed: {e}")
            return False

    def fetch_product_data_browser(self, page, url):
        TARGET_KEYWORD = "graphql.json?opName=colorwayProducts"
        TARGET_HOST = "alo-yoga.myshopify.com"
        colorway_data = {}
        data_received = False
        
        def handle_response(response):
            nonlocal colorway_data, data_received
            if TARGET_KEYWORD in response.url and TARGET_HOST in response.url:
                try:
                    response_text = response.text()
                    json_body = json.loads(response_text)
                    colorway_data.update(json_body)
                    data_received = True
                    logging.info(f"[{self.country}] Successfully captured network response")
                except Exception as e:
                    logging.error(f"[{self.country}] Response processing error: {e}")

        page.on("response", handle_response)
        
        try:
            page.goto(url, timeout=30000)
            wait_time = 0
            while not data_received and wait_time < 15:
                time.sleep(1)
                wait_time += 1
            page.remove_listener("response", handle_response)
            return colorway_data if data_received else None
        except Exception as e:
            logging.error(f"[{self.country}] Error in network interception: {e}")
            return None

    def scrape_product_browser(self, page, gender, category, url):
        try:
            if not self._should_process_url(url):
                return

            product_id = url.split('/_/')[0].split('/')[-1]
            logging.info(f"[{self.country}] NORMAL - Processing {gender}/{category}/{product_id}")

            data = self.fetch_product_data_browser(page, url)
            
            # Fallback to __NEXT_DATA__
            if not data:
                logging.warning(f"[{self.country}] Network interception failed, trying __NEXT_DATA__")
                try:
                    script_content = page.evaluate("document.getElementById('__NEXT_DATA__')?.textContent")
                    if script_content:
                        json_data = json.loads(script_content)
                        data = json_data.get('props', {}).get('pageProps', {}).get('initialStoreState', {}).get('productDetailPage', {}).get('current', {})
                except Exception as e:
                    logging.error(f"[{self.country}] __NEXT_DATA__ fallback failed: {e}")
            
            if data:
                self._save_product_data(gender, category, product_id, data, url)
                logging.info(f"[{self.country}] NORMAL - Saved {gender}/{category}/{product_id}")
            else:
                logging.warning(f"[{self.country}] NORMAL - No data for {url}")
                self._save_global_progress(url, success=False)

        except Exception as e:
            logging.error(f"[{self.country}] Error processing {url}: {e}")
            self._save_global_progress(url, success=False)

    def process_url(self, page, gender, category, url):
        try:
            self.scrape_product_browser(page, gender, category, url)
        except Exception as e:
            logging.error(f"[{self.country}] Error processing {url}: {e}")

# --- WORKER FUNCTIONS ---
def worker_api_fast(country, url_tasks, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, mode='api'):
    scraper = ProductScraper(country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, mode)
    asyncio.run(scraper.run_concurrent_api(url_tasks))

def worker_browser_multiple(country, queue, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, browser_id):
    scraper = ProductScraper(country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, 'normal')
    
    with sync_playwright() as playwright:
        browser = None
        context = None
        page = None
        
        try:
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context(user_agent=random.choice(scraper.USER_AGENTS))
            page = context.new_page()
            
            if scraper.initialize_browser_with_country(page):
                logging.info(f"[{country}] Browser {browser_id} initialized successfully")
                
                while True:
                    try:
                        task = queue.get(timeout=30)
                        if task is None:
                            break
                        gender, category, url = task
                        scraper.process_url(page, gender, category, url)
                        queue.task_done()
                    except Exception as e:
                        logging.error(f"[{country}] Browser {browser_id} error: {e}")
                        # Recreate browser on error
                        try:
                            page.close(); context.close(); browser.close()
                        except: pass
                        try:
                            browser = playwright.chromium.launch(headless=False)
                            context = browser.new_context(user_agent=random.choice(scraper.USER_AGENTS))
                            page = context.new_page()
                            scraper.initialize_browser_with_country(page)
                        except: break
            
        except Exception as e:
            logging.error(f"[{country}] Worker {browser_id} fatal error: {e}")
        finally:
            try: page.close(); context.close(); browser.close()
            except: pass

# --- MAIN PROCESS CONTROL ---
def process_mode_fast(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, mode='api'):
    logging.info(f"Starting {mode.upper()} mode processing...")
    multiprocessing.freeze_support()
    processes = []
    any_work_to_do = False
    
    for country, config in CONFIG.items():
        url_file = Path(f"{country}/{TODAY_DATE}/Item_urls/{country}_product_links.json")
        if not url_file.exists():
            continue
            
        with open(url_file) as f:
            urls_dict = json.load(f)
        
        scraper = ProductScraper(country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, mode)
        
        if mode in ['api', 'sale_api']:
            url_tasks = []
            for gender, categories in urls_dict.items():
                for category, urls in categories.items():
                    for url in urls:
                        if scraper._should_process_url(url):
                            url_tasks.append((gender, category, url))
            
            if url_tasks:
                any_work_to_do = True
                process = multiprocessing.Process(
                    target=worker_api_fast,
                    args=(country, url_tasks, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, mode)
                )
                processes.append(process)
                process.start()
        else:
            urls_to_process = []
            for gender, categories in urls_dict.items():
                for category, urls in categories.items():
                    for url in urls:
                        if scraper._should_process_url(url):
                            urls_to_process.append((gender, category, url))
            
            if urls_to_process:
                any_work_to_do = True
                queue = multiprocessing.JoinableQueue()
                for item in urls_to_process: queue.put(item)
                for _ in range(config['browsers']): queue.put(None)
                
                for browser_id in range(config['browsers']):
                    process = multiprocessing.Process(
                        target=worker_browser_multiple,
                        args=(country, queue, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, browser_id)
                    )
                    processes.append(process)
                    process.start()

    if not any_work_to_do:
        logging.info(f"{mode.upper()} mode skipped - no URLs to process")
        return
    
    for process in processes:
        process.join()
    logging.info(f"{mode.upper()} mode processing completed")

def check_failed_urls_exist(CONFIG, TODAY_DATE):
    """Helper to check if there are any failed URLs remaining"""
    total_failed = 0
    for country in CONFIG:
        fpath = Path(f"{CONFIG[country]['data_dir']}/{TODAY_DATE}/Json_data/{country}_global_progress.json")
        if fpath.exists():
            lock = FileLock(str(fpath))
            with lock:
                try:
                    with open(fpath, 'r') as f:
                        data = json.load(f)
                        total_failed += len(data.get("failed_processed", []))
                except: pass
    return total_failed

def get_product_data(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, re_run=False):
    # Clear old files if rerun request
    if re_run:
        for country in CONFIG.keys():
            output_dir = Path(f"{CONFIG[country]['data_dir']}/{TODAY_DATE}/Json_data")
            for pf in output_dir.glob(f"{country}_product_progress_*.log"): pf.unlink(missing_ok=True)
            (output_dir / f"{country}_global_progress.json").unlink(missing_ok=True)
            (output_dir / f"{country}_global_progress.json.lock").unlink(missing_ok=True)

    start_time = time.time()
    
    # 1. Run Standard Modes
    for mode in ['api', 'sale_api', 'normal']:
        process_mode_fast(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, mode)
    
    # 2. Retry Mechanism (Normal Mode Only, Max 3 Times)
    logging.info("--- Starting Retry Phase for Failed Items ---")
    for attempt in range(3):
        failed_count = check_failed_urls_exist(CONFIG, TODAY_DATE)
        
        if failed_count == 0:
            logging.info("No failed items left to retry. Finishing.")
            break
            
        logging.info(f"Retry Attempt {attempt + 1}/3: Found {failed_count} failed items. Retrying in NORMAL mode...")
        
        # Force run in NORMAL mode. 
        # The scraper's internal logic (_should_process_url) automatically checks 
        # if the URL is already successful. If it failed previously, it won't be in 'success', 
        # so it will be processed again here.
        process_mode_fast(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, mode='normal')

    logging.info(f"All product data collection completed in {time.time() - start_time:.2f} seconds")
