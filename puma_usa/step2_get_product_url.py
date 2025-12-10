import json
import time
import logging
import multiprocessing
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from multiprocessing import Queue, Lock
from urllib.parse import urljoin
import requests
import random
from urllib.parse import urlparse
from validations import refresh_token, check_token_expired


# Set up logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ScraperManager:
    def __init__(self, country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, use_api=True):
        self.country = country
        self.config = CONFIG[country]
        self.today = TODAY_DATE
        self.use_api = use_api
        self.base_url = COUNTRIES[country]
        self.USER_AGENTS = USER_AGENTS
        self.prefix = self.config.get('prefix', '')
        self.token = self.config.get('token', '')
        self.refresh_token = self.config.get('refresh_token', '')
        self.max_retries = self.config.get('max_retries', 5)

        
        # Original file structure maintained
        self.output_dir = Path(f"{self.config['data_dir']}/{self.today}/Item_urls")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Files for persistent storage
        self.results_file = self.output_dir / f"{self.country}_product_links.json"
        self.progress_file = self.output_dir / f"{self.country}_progress.log"
        
        # Load existing results and progress
        self.existing_results = self._load_existing_results()
        self.completed_urls = self._load_completed_urls()
        
        # API session for requests
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": random.choice(self.USER_AGENTS)
        })

    def _load_existing_results(self):
        """Load previously scraped results if they exist"""
        if self.results_file.exists():
            with open(self.results_file, 'r') as f:
                return json.load(f)
        return {}

    def _load_completed_urls(self):
        """Load URLs that have already been processed"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _save_results(self, gender, category, product_urls):
        """Save results incrementally - maintaining original structure"""
        with Lock():  # Thread-safe file operations
            # Load current results
            current_results = self._load_existing_results()
            
            # Update results
            if gender not in current_results:
                current_results[gender] = {}
            current_results[gender][category] = product_urls
            
            # Save to file
            with open(self.results_file, 'w') as f:
                json.dump(current_results, f, indent=4)
            
            # Update progress log
            with open(self.progress_file, 'a') as f:
                f.write(f"{gender}|{category}\n")
    
    def extract_handle_from_url(self, url):
        """
        Extracts the relevant path from a URL, removing the domain and the '/us/en' prefix.
        
        Example:
        'https://us.puma.com/us/en/women/best-sellers' -> '/women/best-sellers'
        """
        # Parse the URL into its components (scheme, netloc, path, etc.)
        parsed_url = urlparse(url)
        
        # Get the path component (e.g., '/us/en/women/best-sellers')
        path = parsed_url.path
        
        # Define the prefix we want to remove from the path
        prefix_to_remove = self.prefix
        
        # If the path starts with our prefix, remove it
        if path.startswith(prefix_to_remove):
            # Using .removeprefix() is clean and explicit (available in Python 3.9+)
            return path.removeprefix(prefix_to_remove)
            
        # As a fallback for older Python or if prefix doesn't exist, you could use replace:
        # return path.replace(prefix_to_remove, '', 1)
        
        return path # Return the original path if the prefix isn't there
    
    def get_total_products_api(self, url_path, retry=0):
        """
        Get the total product count for a given category URL path from the Puma GraphQL API.
        
        Args:
            url_path (str): The category path, e.g., '/women/best-sellers'
        """
        # The API endpoint for the GraphQL service
        api_url = "https://us.puma.com/api/graphql"

        # Define the necessary headers, including Authorization for the Bearer Token
        headers = {
            "Authorization": f"Bearer {self.token}", # Assumes your token is in self.token
            "Locale": "en-US",
            "Content-Type": "application/json"
        }

        # The complex GraphQL query string provided
        graphql_query = """
        query CategoryPLP($url: String!, $isDraft: String, $sort: String, $filters: [FilterInputOption!]!, $expansions: [ProductSearchExpansion!], $includeCategoryMetadata: Boolean = true, $offset: Int!, $limit: Int!, $preview: PreviewInput) {
        categoryByUrl(url: $url, preview: $preview) {
            products(input: {limit: $limit, offset: $offset, filters: $filters, sort: $sort, expansions: $expansions, includeCategoryMetadata: $includeCategoryMetadata, isDraft: $isDraft, useScapiSearch: true}) {
            ...PaginatedOutputMetadataFragment @include(if: $includeCategoryMetadata)
            }
        }
        }
        fragment PaginatedOutputMetadataFragment on PaginatedOutput {
        totalCount
        }
        """
        # Construct the JSON payload with the operation name, query, and variables
        payload = {
            "operationName": "CategoryPLP",
            "query": graphql_query,
            "variables": {
                "url": url_path, # Dynamically insert the URL path here
                "limit": 1,      # We only need the count, so we request just 1 item for efficiency
                "offset": 0,
                "filters": [],
                "includeCategoryMetadata": True,
                "isDraft": "false",
                "preview": {
                    "global": False
                }
            }
        }

        try:
            # Make the POST request to the GraphQL API
            response = self.session.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            # Raise an exception for bad status codes (like 401 Unauthorized or 500 Server Error)
            response.raise_for_status()
            
            data = response.json()

            token_expired, error = check_token_expired(data)
            if token_expired and retry < self.max_retries:
                if error == 'Token expired':
                    self.token = refresh_token(self.refresh_token)
                    print("token refreshed")
                elif error == "Internal server error":
                    logging.error(f"[{self.country}] Internal server error for {url_path}.")
                return self.get_total_products_api(url_path, retry + 1)
            
            
            # Safely navigate the JSON response to extract the total product count
            # The path is now data -> categoryByUrl -> products -> totalCount
            total_count = data.get("data", {}).get("categoryByUrl", {}).get("products", {}).get("totalCount", 0)
            return total_count

        except Exception as e:
            logging.error(f"Error fetching product count for path '{url_path}': {e}")
            return 0
    
    def extract_product_urls_api(self, handle, retry=0):
        """Extract product URLs using API and ensure proper country prefix"""
        product_urls = []
        offset = 0
        limit = 24
        
        while True:
            api_url = "https://us.puma.com/api/graphql"

            # Define the necessary headers, including Authorization for the Bearer Token
            headers = {
                "Authorization": f"Bearer {self.token}", # Assumes your token is in self.token
                "Locale": "en-US",
                "Content-Type": "application/json"
            }

            # The complex GraphQL query string provided
            graphql_query = """
                query CategoryPLP($url: String!, $limit: Int!, $offset: Int!, 
                $filters: [FilterInputOption!]!) 
                {\n  categoryByUrl(url: $url) 
                {\n    products(input: { limit: $limit, offset: $offset, filters: $filters }) 
                {\n      nodes {\n        masterId\n      }\n    }\n  }\n}
            """
            # Construct the JSON payload with the operation name, query, and variables
            payload = {
                "operationName": "CategoryPLP",
                "query": graphql_query,
                "variables": {
                    "url": handle, # Dynamically insert the URL path here
                    "limit": limit,
                    "offset": offset,
                    "filters": [],
                }
            }

            try:
                # Make the POST request to the GraphQL API
                response = self.session.post(
                    api_url,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                # Raise an exception for bad status codes (like 401 Unauthorized or 500 Server Error)
                response.raise_for_status()
                
                data = response.json()

                token_expired, error = check_token_expired(data)
                if token_expired and retry < self.max_retries:
                    if error == 'Token expired':
                        self.token = refresh_token(self.refresh_token)
                    elif error == 'Internal server error':
                        print(f"[{self.country}] Internal server error for {handle}.")
                    return self.extract_product_urls_api(handle, retry + 1)

                nodes = data.get("data", {}).get("categoryByUrl", {}).get("products", {}).get("nodes", [])
                
                if not nodes:
                    break
                
                urls = [node.get("masterId") for node in nodes if node.get("masterId")]
                # Convert URLs to country-specific format
                product_urls.extend(urls)
                
                offset += limit    
            except Exception as e:
                logging.error(f"Error fetching API data: {e}")
                break
        
        return product_urls

    def process_url(self, page, gender, category, url):
        """Process a single URL and save results immediately"""
        if f"{gender}|{category}" in self.completed_urls:
            logging.info(f"[{self.country}] Skipping already processed {gender}/{category}")
            return

        logging.info(f"[{self.country}] Processing {gender}/{category}")
        
        try:
            if self.use_api:
                # API-based processing
                handle = self.extract_handle_from_url(url)
                logging.info(f"[{self.country}] Using API for {handle}")
                
                count = self.get_total_products_api(handle)
                print("count", count)
                if count == 0:
                    logging.warning(f"[{self.country}] No products found for {handle}")
                    return
                
                logging.info(f"[{self.country}] Found {count} products via API")
                links = self.extract_product_urls_api(handle)
                
            else:
                # Browser-based processing (original method)
                page.goto(url, wait_until="load", timeout=60000)
                
                # Close popup if exists
                try:
                    page.click('.closeButton__onjV4S', timeout=5000)
                    logging.info(f"[{self.country}] Closed popup/modal")
                except:
                    pass

                # Get total product count
                count_element = page.query_selector('p.OneLinkTx')
                if count_element:
                    count_text = count_element.inner_text()
                    count = int(count_text.split('of')[-1].strip().split()[0])
                    pages = (count // 12) + (1 if count % 12 else 0)
                    logging.info(f"[{self.country}] Found {count} products, {pages} pages")
                else:
                    pages = 1
                    logging.warning(f"[{self.country}] Could not find product count, defaulting to 1 page")

                # Click "Load More" until all products are loaded
                for i in range(pages):
                    try:
                        # Scroll to the bottom to ensure all products are loaded
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)  # Wait for products to load
                        page.click('button[class*="pagination_button"][aria-disabled="false"]', timeout=5000)
                        logging.info(f"[{self.country}] Clicked 'Load More' button {i+1}/{pages}")
                        time.sleep(2)
                    except:
                        break

                # Get all product links
                links = set()
                product_links = page.query_selector_all('a.link.product-tile__image-link')
                for link in product_links:
                    href = link.get_attribute('href')
                    if href:
                        full_url = urljoin(self.config['base_url'], href)
                        links.add(full_url)
                links = list(links)

            # Save results immediately (maintaining original structure)
            self._save_results(gender, category, links)
            logging.info(f"[{self.country}] Saved {len(links)} products for {gender}/{category}")

        except Exception as e:
            logging.error(f"[{self.country}] Error processing {url}: {str(e)}")

def worker(country, queue, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, use_api=True):
    """Worker process that handles URLs from the queue"""
    scraper = ScraperManager(country, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, use_api)
    
    if not use_api:
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
                    scraper.process_url(page, gender, category, url)
                    queue.task_done()
            finally:
                context.close()
                browser.close()
    else:
        # API mode - no browser needed
        try:
            while True:
                task = queue.get()
                if task is None:  # Sentinel value to stop
                    break
                gender, category, url = task
                scraper.process_url(None, gender, category, url)  # page=None for API mode
                queue.task_done()
        finally:
            pass

def get_product_urls(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES):
    """Main function to coordinate scraping for all countries"""
    start_time = time.time()
    multiprocessing.freeze_support()
    
    processes = []
    queues = {}
    
    # Create queues and add tasks for each country
    for country, config in CONFIG.items():
        # Load category URLs
        with open(f'{country}/{TODAY_DATE}/{country}_category_links.json') as f:
            url_dict = json.load(f)
        
        # Create queue and add tasks
        queue = multiprocessing.JoinableQueue()
        for gender, categories in url_dict.items():
            for category, url in categories.items():
                queue.put((gender, category, url))
        
        # Add sentinel values for each worker
        for _ in range(config['browsers']):
            queue.put(None)
        
        # Start worker processes
        for _ in range(config['browsers']):
            process = multiprocessing.Process(
                target=worker,
                args=(country, queue, CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, config['api'])
            )
            processes.append(process)
            process.start()
        
        queues[country] = queue
    
    # Wait for all processes to complete
    for process in processes:
        process.join()
    
    end_time = time.time()
    logging.info(f"Scraping completed in {end_time - start_time:.2f} seconds")
    logging.info(f"Method used: {'API' if config['api'] else 'Browser'}")
