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
import threading
from validations import refresh_token, check_token_expired

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Use threading lock instead of multiprocessing Manager to avoid Windows issues
GLOBAL_LOCK = threading.Lock()

class ProductScraper:
    def __init__(self, country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES):
        self.country = country
        self.config = CONFIG[country]
        self.today = TODAY_DATE
        self.base_url = COUNTRIES[country]
        self.USER_AGENTS = USER_AGENTS
        
        # Single output directory for all modes - Json_data folder
        self.output_dir = Path(f"{self.config['data_dir']}/{self.today}/Json_data")
        self.progress_file = self.output_dir / f"{self.country}_product_progress.log"
        self.output_dir.mkdir(parents=True, exist_ok=True)
            
        # Load progress for this mode and globally
        self.completed_urls = self._load_completed_urls()
        
        # aiohttp session for API calls
        self.session = None

        self.prefix = self.config.get('prefix', '')
        self.token = self.config.get('token', '')
        self.refresh_token = self.config.get('refresh_token', '')
        self.max_retries = self.config.get('max_retries', 5)
        self.use_api = self.config.get('api', True)

        # Add an asyncio.Lock for controlling token refreshes
        self.token_refresh_lock = asyncio.Lock()
        self.concurrency_limit = self.config.get('api_concurrency', 25)
        self.semaphore = asyncio.Semaphore(self.concurrency_limit)

    def _load_completed_urls(self):
        """Load already processed URLs for this specific mode"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _should_process_url(self, url):
        """Determine if URL should be processed based on mode and previous attempts"""
        # If current mode already processed this URL, skip
        if url in self.completed_urls:
            return False
          
        return True

    def _save_product_data(self, gender, category, product_id, product_data, url):
        """Save product data with proper progress tracking"""
        try:
            # Create directory structure: Json_data/Gender/Category/
            output_path = self.output_dir / gender.upper() / category
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Save individual product file
            product_file = output_path / f"{product_id}.json"
            with open(product_file, 'w') as f:
                json.dump(product_data, f, indent=4)
            
            # Update mode-specific progress
            with GLOBAL_LOCK:
                with open(self.progress_file, 'a') as f:
                    f.write(f"{url}\n")
            
        except Exception as e:
            logging.error(f"[{self.country}] Error saving {product_id}: {e}")

    # API Mode Methods
    async def init_session(self):
        """Initialize aiohttp session"""
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
        """Close aiohttp session"""
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                logging.error(f"Error closing session: {e}")
            self.session = None

    async def fetch_product_data_api(self, style_id, retry_attempt=0):
        """Fetch product data using aiohttp"""
        await self.init_session()
        
        graphql_query = """query CombinedPDP($id: ID!, $viewAt: String) {\n  product(id: $id) 
        {\n    id\n    name\n    header\n    subHeader\n    orderableColorCount\n    productNameTranslated\n    
        description\n    primaryCategoryId\n    productDivision\n    brand\n    disableRatings\n    
        disableReviews\n    amountOfReviews\n    averageRating\n    sizeChartId\n    promotionExclusion\n    
        exploreMoreCTALabel\n    showExploreCollectionCTA\n    exploreMoreCTATargetCategoryID\n    
        orderable\n    productVideos\n    verticalProductVideos\n    ...sizes\n    displayOutOfStock 
        {\n      soldout\n      soldoutWithRecommender\n      comingsoon\n      backsoon\n      presale\n      
        displayValue\n      __typename\n    }\n    colors {\n      name\n      value\n      
        image {\n        href\n        verticalImageHref\n        alt\n        __typename\n      }\n      
        __typename\n    }\n    image {\n      href\n      verticalImageHref\n      alt\n      
        __typename\n    }\n    promotions(page: ProductDetailsPage) {\n      id\n      calloutMessage\n      
        __typename\n    }\n    configureID {\n      enabled\n      productID\n      __typename\n    }\n    
        fitOptions {\n      label\n      masterProduct {\n        id\n        name\n        variations 
        {\n          id\n          colorValue\n          orderable\n          __typename\n        }\n        
        __typename\n      }\n      __typename\n    }\n    variations {\n      ...pdpMandatoryVariantFields\n      
        ...pdpMandatoryExtraVariantFields\n      description\n      isFinalSale\n      returnRuleID\n      
        promotionExclusion\n      specialMessage(viewAt: $viewAt)\n      ean\n      validUntil\n      
        isAppExclusive\n      percentageDiscountBadge\n      salePrice\n      styleNumber\n      
        materialComposition\n      orderable\n      modelMeasurementText\n      taxDisplayMsg\n      
        appOnlyDateTimeFrom\n      appOnlyDateTimeTo\n      productStory {\n        longDescription\n        
        materialComposition\n        careInstructions\n        manufacturerInfo {\n          manufacturerAddress 
        {\n            label\n            content\n            __typename\n          }\n          countryOfOrigin 
        {\n            label\n            content\n            __typename\n          }\n          __typename\n        }\n        
        productKeywords\n        __typename\n      }\n      badges {\n        id\n        label\n        
        __typename\n      }\n      productPrice {\n        price\n        salePrice\n        promotionPrice\n        
        isSalePriceElapsed\n        tax\n        taxRate\n        bestPrice\n        __typename\n      }\n      
        displayOutOfStock {\n        soldout\n        soldoutWithRecommender\n        comingsoon\n        backsoon\n        
        presale\n        displayValue\n        validTo\n        __typename\n      }\n      manufacturerInfo 
        {\n        manufacturerAddress {\n          label\n          content\n          __typename\n        }\n        
        countryOfOrigin {\n          label\n          content\n          __typename\n        }\n        
        __typename\n      }\n      myCustomizer {\n        enabled\n        iframeID\n        startPoint\n        
        __typename\n      }\n      configureID {\n        enabled\n        productID\n        __typename\n      }\n      
        promotions(page: ProductDetailsPage) {\n        id\n        calloutMessage\n        __typename\n      }\n      
        __typename\n    }\n    __typename\n  }\n}\n\nfragment sizes on Product {\n  productMeasurements 
        {\n    metric\n    imperial\n    __typename\n  }\n  __typename\n}\n\nfragment pdpMandatoryExtraVariantFields on Variant 
        {\n  id\n  sizeGroups {\n    label\n    description\n    sizes {\n      id\n      label\n      
        value\n      productId\n      orderable\n      maxOrderableQuantity\n      __typename\n    }\n    
        __typename\n  }\n  __typename\n}\n\nfragment mandatoryMasterFields on Product 
        {\n  name\n  id\n  header\n  subHeader\n  orderableColorCount\n  displayOutOfStock 
        {\n    soldout\n    soldoutWithRecommender\n    comingsoon\n    backsoon\n    presale\n    displayValue\n    
        __typename\n  }\n  colors {\n    name\n    value\n    image {\n      href\n      verticalImageHref\n      alt\n      
        __typename\n    }\n    __typename\n  }\n  image {\n    href\n    verticalImageHref\n    alt\n    
        __typename\n  }\n  showExploreCollectionCTA\n  __typename\n}\n\nfragment pdpMandatoryVariantFields on Variant 
        {\n  id\n  masterId\n  variantId\n  name\n  header\n  subHeader\n  price\n  colorValue\n  colorName\n  ean\n  
        preview\n  images {\n    alt\n    href\n    verticalImageHref\n    __typename\n  }\n  __typename\n}"""
        
        payload = {
            "operationName": "CombinedPDP",
            "query": graphql_query,
             "variables": {
                "id": style_id,
                "viewAt": None
            }
        }


        

        token_for_this_request = self.token
        
        headers = {
            "Authorization": f"Bearer {token_for_this_request}", # Assumes your token is in self.token
            "Locale": "en-US",
            "Content-Type": "application/json"
        }

        try:
            async with self.session.post(
                "https://us.puma.com/api/graphql",
                ssl=False,
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    status, error = check_token_expired(data)
                    if status:
                        if retry_attempt < self.max_retries:
                            if error == 'Token expired':
                                # --- START of LOCK LOGIC ---
                                # Acquire the lock to ensure only one task can refresh at a time
                                async with self.token_refresh_lock:
                                    # DOUBLE-CHECK: After acquiring the lock, check if the token was
                                    # already refreshed by another task while we were waiting.
                                    if token_for_this_request == self.token:
                                        logging.warning(f"[{self.country}] Token expired for {style_id}. I am the designated refresher.")
                                        new_token = refresh_token(self.refresh_token)
                                        if new_token:
                                            self.token = new_token
                                            logging.info(f"[{self.country}] New token acquired.")
                                        else:
                                            logging.error(f"[{self.country}] Failed to get a new token.")
                                            return None
                                    else:
                                        logging.info(f"[{self.country}] Token was already refreshed by another task for {style_id}. Retrying.")
                                # --- END of LOCK LOGIC ---
                            elif error == "Internal server error":
                                logging.error(f"[{self.country}] Internal server error for {style_id}.")
                                return None

                            # Retry the entire function call
                            return await self.fetch_product_data_api(style_id, retry_attempt + 1)
                        else:
                            logging.error(f"[{self.country}] Max retries reached for {style_id}.")
                            return None

                    return data # Success
                else:
                    logging.error(f"API error {response.status} for {style_id}")
                    return None
        except Exception as e:
            logging.error(f"Network error for {style_id}: {e}")
        

    async def process_url_api(self, gender, category, url, retry=0):
        """Process URL using API mode with smart continuation"""
        try:
            # Check if we should process this URL
            if not self._should_process_url(url):
                return
            
            data = await self.fetch_product_data_api(url)
            edges = data.get("data", {}) if data else None
            
            if edges:
                self._save_product_data(gender, category, url, data, url)
                logging.info(f"[{self.country}] - Saved {gender}/{category}/{url}")
            else:
                logging.warning(f"[{self.country}] - No product data for: {url}")
                
        except Exception as e:
            logging.error(f"[{self.country}] Error processing {url}: {e}")

    async def run_concurrent_api(self, url_tasks):
        """Run concurrent API processing with smart filtering"""
        start_time = time.time()
        
        # Filter URLs based on what should be processed
        new_tasks = []
        for g, c, u in url_tasks:
            if self._should_process_url(u):
                new_tasks.append((g, c, u))
        
        if not new_tasks:
            logging.info(f"[{self.country}] No URLs to process")
            return
        
        logging.info(f"[{self.country}] - Processing {len(new_tasks)} URLs (skipped {len(url_tasks) - len(new_tasks)} already processed)")
        
        # Process all URLs concurrently
        async def wrapped_task(gender, category, style_id):
            async with self.semaphore:
                # Add a small, random delay (jitter) to avoid robotic timing
                await asyncio.sleep(random.uniform(0.5, 1.5))
                return await self.process_url_api(gender, category, style_id)
            
        # await asyncio.gather(*(self.process_url_api(gender, category, url) for gender, category, url in new_tasks))
        await asyncio.gather(*(wrapped_task(gender, category, style_id) for gender, category, style_id in new_tasks))
        
        duration = time.time() - start_time
        logging.info(f"[{self.country}] completed in {duration:.2f} seconds")
        
        await self.close_session()

    # Normal Mode Methods
    def handle_popups(self, page):
        """Handle popups efficiently"""
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

        # Handle iframe popups
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
        """Select country manually with retry logic"""
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
        """Initialize browser with country setup"""
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
        """Fetch product data with network interception - fixed version"""
        TARGET_KEYWORD = "graphql.json?opName=colorwayProducts"
        TARGET_HOST = "alo-yoga.myshopify.com"
        
        colorway_data = {}
        data_received = False
        
        def handle_response(response):
            nonlocal colorway_data, data_received
            if TARGET_KEYWORD in response.url and TARGET_HOST in response.url:
                try:
                    # Get response text immediately to avoid Protocol error
                    response_text = response.text()
                    json_body = json.loads(response_text)
                    colorway_data.update(json_body)
                    data_received = True
                    logging.info(f"[{self.country}] Successfully captured network response")
                except Exception as e:
                    logging.error(f"[{self.country}] Response processing error: {e}")
                    # Try fallback method
                    try:
                        json_body = response.json()
                        colorway_data.update(json_body)
                        data_received = True
                    except Exception as e2:
                        logging.error(f"[{self.country}] Fallback also failed: {e2}")

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
        """Scrape product using browser with smart continuation and fallback"""
        try:
            # Check if we should process this URL
            if not self._should_process_url(url):
                return

            product_id = url.split('/_/')[0].split('/')[-1]
            logging.info(f"[{self.country}] NORMAL - Processing {gender}/{category}/{product_id}")

            # Try network interception first
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
        """Process URL for browser mode"""
        try:
            self.scrape_product_browser(page, gender, category, url)
        except Exception as e:
            logging.error(f"[{self.country}] Error processing {url}: {e}")

def worker_api_fast(country, url_tasks, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES):
    """Fast worker for API modes"""
    scraper = ProductScraper(country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES)
    asyncio.run(scraper.run_concurrent_api(url_tasks))

def worker_browser_multiple(country, queue, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, browser_id):
    """Individual browser worker"""
    scraper = ProductScraper(country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES)
    
    with sync_playwright() as playwright:
        browser = None
        context = None
        page = None
        
        try:
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context(user_agent=random.choice(scraper.USER_AGENTS))
            page = context.new_page()
            
            success = scraper.initialize_browser_with_country(page)
            if not success:
                logging.error(f"[{country}] Browser {browser_id} initialization failed")
                return
            
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
                    # Try to recreate browser on major errors
                    if browser and not page.is_closed():
                        try:
                            page.close()
                            context.close()
                            browser.close()
                        except:
                            pass
                        
                        try:
                            browser = playwright.chromium.launch(headless=False)
                            context = browser.new_context(user_agent=random.choice(scraper.USER_AGENTS))
                            page = context.new_page()
                            scraper.initialize_browser_with_country(page)
                            logging.info(f"[{country}] Browser {browser_id} recreated")
                        except Exception as recreate_error:
                            logging.error(f"[{country}] Failed to recreate browser {browser_id}: {recreate_error}")
                            break
                    
        except Exception as e:
            logging.error(f"[{country}] Worker {browser_id} fatal error: {e}")
        finally:
            try:
                if page and not page.is_closed():
                    page.close()
                if context:
                    context.close()
                if browser:
                    browser.close()
            except:
                pass

def process_mode_fast(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES):
    """Fast processing mode with smart continuation and mode skipping"""
    
    multiprocessing.freeze_support()
    processes = []

    for country, config in CONFIG.items():
        url_file = Path(f"{country}/{TODAY_DATE}/Item_urls/{country}_product_links.json")
        
        if not url_file.exists():
            logging.warning(f"No product URLs found for {country} on {TODAY_DATE}")
            continue
            
        with open(url_file) as f:
            urls_dict = json.load(f)
        
        # Pre-check if there's any work to do for this country and mode
        scraper = ProductScraper(country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES)
        
        if config['api']:
            # Check if any URLs need processing
            url_tasks = []
            for gender, categories in urls_dict.items():
                for category, urls in categories.items():
                    for url in urls:
                        if scraper._should_process_url(url):
                            url_tasks.append((gender, category, url))
            
            if not url_tasks:
                logging.info(f"[{country}] No URLs to process")
                continue
                        
            # Start API worker
            process = multiprocessing.Process(
                target=worker_api_fast,
                args=(country, url_tasks, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES)
            )
            processes.append(process)
            process.start()
        else:
            # Browser mode - check if any URLs need processing
            urls_to_process = []
            for gender, categories in urls_dict.items():
                for category, urls in categories.items():
                    for url in urls:
                        if scraper._should_process_url(url):
                            urls_to_process.append((gender, category, url))
            
            if not urls_to_process:
                logging.info(f"[{country}] No URLs to process")
                continue
            
            # Create queue only with URLs that need processing
            queue = multiprocessing.JoinableQueue()
            for gender, category, url in urls_to_process:
                queue.put((gender, category, url))
            
            # Add sentinel values for each worker
            for _ in range(config['browsers']):
                queue.put(None)
            
            # Start browser workers
            for browser_id in range(config['browsers']):
                process = multiprocessing.Process(
                    target=worker_browser_multiple,
                    args=(country, queue, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, browser_id)
                )
                processes.append(process)
                process.start()
    
    # Wait for all processes to complete
    for process in processes:
        process.join()
    
    logging.info(f"processing completed")

def get_product_data(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, re_run=False):
    """Main function with smart continuation and re-run support"""
    
    # If re_run is True, clear all progress files
    if re_run:
        for country in CONFIG.keys():
            output_dir = Path(f"{CONFIG[country]['data_dir']}/{TODAY_DATE}/Json_data")
            progress_files = [
                output_dir / f"{country}_product_progress.log"
            ]
            for pf in progress_files:
                if pf.exists():
                    pf.unlink()
                    logging.info(f"Cleared progress file: {pf}")
    
    start_time = time.time()
        
    process_mode_fast(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES)
    
    total_duration = time.time() - start_time
    logging.info(f"All product data collection completed in {total_duration:.2f} seconds")

