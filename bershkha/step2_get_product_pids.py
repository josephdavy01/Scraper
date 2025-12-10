import os
import json
import logging
import multiprocessing
import asyncio
import random
from playwright.async_api import async_playwright
from validations import save_json, append_log, load_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ProductUrlScraper:
    def __init__(self, country, config, today_date):
        self.country = country
        self.config = config
        self.today_date = today_date
        
        self.base_dir = f"{country}/{today_date}/Item_urls"
        os.makedirs(self.base_dir, exist_ok=True)
        
        self.results_file = os.path.join(self.base_dir, f"{country}_product_ids.json")
        self.success_log = os.path.join(self.base_dir, "success_url.log")
        self.fail_log = os.path.join(self.base_dir, "fail_url.log")

    def get_processed_keys(self):
        processed = set()
        if os.path.exists(self.success_log):
            with open(self.success_log, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('|')
                    if len(parts) >= 2:
                        processed.add(f"{parts[0]}_{parts[1]}")
        return processed

    def merge_and_save(self, new_data):
        full_data = load_json(self.results_file)
        for gender, cats in new_data.items():
            if gender not in full_data:
                full_data[gender] = {}
            for cat, ids in cats.items():
                full_data[gender][cat] = ids
        save_json(self.results_file, full_data)

async def fetch_category_data(page, url):
    """
    Navigates to the URL and extracts JSON content from <pre> tag.
    Matches the logic from the user's old code.
    """
    try:
        await page.goto(url) # Default wait_until='load'
        
        content = await page.locator("pre").text_content()
        
        if not content:
            # Fallback: Try reading body text
            content = await page.evaluate("document.body.innerText")
            
        if not content:
            return None
            
        return json.loads(content)
    except Exception as e:
        raise e

async def worker_task(queue, scraper, context):
    """
    Worker that maintains a single page and processes tasks from the queue.
    """
    page = await context.new_page()
    
    while True:
        task = await queue.get()
        if task is None:
            queue.task_done()
            break
            
        gender, cat_name, cat_id = task
        
        store_id = scraper.config['cid']
        lang = "-15" if scraper.country == "USA" else "-1"
        url = f'https://www.bershka.com/itxrest/3/catalog/store/{store_id}/category/{cat_id}/product?languageId={lang}&showProducts=false&appId=1'
        
        retries = 3
        success = False
        
        for attempt in range(retries):
            try:
                # Random delay
                await asyncio.sleep(random.uniform(1.0, 3.0))
                
                data = await fetch_category_data(page, url)
                
                if data:
                    pids_list = data.get('productIds', [])
                    
                    if pids_list:
                        chunk = {gender: {cat_name: pids_list}}
                        scraper.merge_and_save(chunk)
                        append_log(scraper.success_log, f"{gender}|{cat_name}|count:{len(pids_list)}")
                        logging.info(f"[{scraper.country}] OK: {gender} > {cat_name} ({len(pids_list)} items)")
                    else:
                        append_log(scraper.success_log, f"{gender}|{cat_name}|count:0")
                        logging.info(f"[{scraper.country}] Empty: {gender} > {cat_name}")
                    
                    success = True
                    break
                else:
                    raise Exception("Empty data received")

            except Exception as e:
                if attempt < retries - 1:
                    logging.warning(f"[{scraper.country}] Retry {attempt+1}/{retries} for {cat_name}: {e}")
                    await asyncio.sleep(2)
                else:
                    err_msg = str(e)
                    append_log(scraper.fail_log, f"{gender}|{cat_name}|CID:{cat_id}|{err_msg}")
                    logging.error(f"[{scraper.country}] Failed: {gender} > {cat_name} - {err_msg}")
        
        queue.task_done()
    
    await page.close()

async def worker_country(country, config, today_date):
    scraper = ProductUrlScraper(country, config, today_date)
    
    cat_file = f"{country}/{today_date}/Category/{country}_category_urls.json"
    if not os.path.exists(cat_file):
        logging.error(f"[{country}] Category file not found: {cat_file}")
        return

    cat_data = load_json(cat_file)
    processed_keys = scraper.get_processed_keys()
    
    if processed_keys:
        logging.info(f"[{country}] Resuming... {len(processed_keys)} categories already done.")
    
    # Create Queue
    queue = asyncio.Queue()
    tasks_count = 0
    
    # IMPORTANT: Skip categories with null URLs (they cause 404 errors)
    for gender, subcats in cat_data.items():
        for cat_name, details in subcats.items():
            if not isinstance(details, dict): 
                continue
            if f"{gender}_{cat_name}" in processed_keys: 
                continue
            
            cat_id = details.get('id') or details.get('cid')
            if cat_id:
                queue.put_nowait((gender, cat_name, cat_id))
                tasks_count += 1
    
    if tasks_count == 0:
        logging.info(f"[{country}] All categories already processed.")
        return

    logging.info(f"[{country}] Starting processing for {tasks_count} categories...")

    async with async_playwright() as p:
        # headless=False as per old code reference
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        # Create Workers (Pages)
        # Using 3 concurrent pages per country
        num_workers = 3
        workers = []
        
        for _ in range(num_workers):
            workers.append(asyncio.create_task(worker_task(queue, scraper, context)))
            
        # Wait for queue to be empty
        await queue.join()
        
        # Stop workers
        for _ in range(num_workers):
            await queue.put(None)
        
        await asyncio.gather(*workers)
        await browser.close()

def run_country_process(country, config, today_date):
    try:
        asyncio.run(worker_country(country, config, today_date))
    except Exception as e:
        logging.error(f"[{country}] Process crashed: {e}")

def get_product_urls(config_dict, today_date):
    logging.info("--- Starting Product ID Extraction (Persistent Page Mode) ---")
    processes = []
    for country, settings in config_dict.items():
        p = multiprocessing.Process(target=run_country_process, args=(country, settings, today_date))
        p.start()
        processes.append(p)
    
    for p in processes:
        p.join()
    logging.info("--- Product ID Extraction Complete ---")