import os
import logging
import multiprocessing
from pathlib import Path
from datetime import datetime
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from validations import save_json, load_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def check_file(gender, category, name, date_subfolder):
    """Check if product JSON file already exists."""
    file_path = date_subfolder / 'Json_data' / gender / category / f'{name}.json'
    return file_path.exists()


async def get_json(page, store_id, country_code, gender, category, plist, date_subfolder):
    """Fetch product data for a list of product IDs."""
    pdlist = []
    failed_pids = []

    for pid in plist:
        if not check_file(gender, category, str(pid), date_subfolder):
            # Construct API URL
            url = f'https://www.bershka.com/itxrest/3/catalog/store/{store_id}/productsArray?productIds={pid}&appId=1&languageId=-1&locale=en_US'
            if country_code == 'us':
                url = f'https://www.bershka.com/itxrest/3/catalog/store/{store_id}/productsArray?productIds={pid}&appId=1&languageId=-15&locale=en_GB'

            success = False
            for attempt in range(3):
                try:
                    await page.goto(url)
                    await page.wait_for_load_state("domcontentloaded", timeout=80000)
                    pre = await page.locator("pre").text_content(timeout=20000)
                    
                    # Parse JSON
                    if isinstance(pre, str):
                        import json
                        json_data = json.loads(pre)
                    else:
                        json_data = pre

                    # Extract product URLs
                    for i in json_data.get('products', [{}])[0].get('bundleProductSummaries', [{}])[0].get('detail', {}).get('colors', []):
                        if json_data['products'][0]['id'] == i['catentryId']:
                            purl = f"https://www.bershka.com/{country_code}/{json_data['products'][0]['name'].lower().replace(' ', '-')}-c0p{i['catentryId']}.html?colorId={i['id']}"
                            pdlist.append(purl)

                    # Save JSON
                    json_file_path = date_subfolder / 'Json_data' / gender / category
                    json_file_path.mkdir(parents=True, exist_ok=True)
                    file_name = json_file_path / f'{pid}.json'
                    save_json(str(file_name), json_data)
                    
                    success = True
                    break

                except PlaywrightTimeoutError:
                    logging.warning(f"[TIMEOUT] Retrying product {pid} (attempt {attempt + 1}/3)...")
                except Exception as e:
                    logging.error(f"[ERROR] Processing product {pid}: {e}")
                    break

            if not success:
                logging.error(f"[FAIL] Giving up on product {pid} after 3 attempts.")
                failed_pids.append(pid)

    # Save failed PIDs
    if failed_pids:
        fail_log_dir = date_subfolder / 'Validation'
        fail_log_dir.mkdir(parents=True, exist_ok=True)
        fail_file = fail_log_dir / f"{gender}_{category}_failed.json"
        save_json(str(fail_file), failed_pids)

    return pdlist


async def process_category(semaphore, browser, store_id, country_code, gender, category, plist, date_subfolder, country):
    """Process a single category with a semaphore."""
    async with semaphore:
        page = await browser.new_page()
        try:
            logging.info(f"[INFO] {country}: Processing {gender} > {category}")
            urls = await get_json(page, store_id, country_code, gender, category, plist, date_subfolder)
            logging.info(f"[DONE] {country}: {gender} > {category}")
            return {
                "category_name": gender,
                "subcategory": category,
                "urls": urls
            }
        finally:
            await page.close()


async def process_country(country, config, today_date):
    """Process product data for a single country."""
    logging.info(f"[START] Processing {country}")
    
    date_subfolder = Path(country) / today_date
    date_subfolder.mkdir(parents=True, exist_ok=True)
    purl_list = []

    # Extract config
    cid_str = config.get('cid', '')
    store_id = cid_str
    base_url = config.get('base_url', '')
    country_code = base_url.split('/')[-2] if base_url else country.lower()
    headless = config.get('headless', False)
    browsers_count = config.get('browsers', 1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless, 
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # Load product IDs
        file_path = Path(country) / today_date / "Item_urls" / f"{country}_product_ids.json"
        pids_dict = load_json(str(file_path))
        
        semaphore = asyncio.Semaphore(browsers_count)
        tasks = []

        for gender in pids_dict:
            logging.info(f"[INFO] {country}: Queueing {gender}")
            for category, plist in pids_dict[gender].items():
                task = process_category(
                    semaphore, browser, store_id, country_code, 
                    gender, category, plist, date_subfolder, country
                )
                tasks.append(task)

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)
        purl_list = list(results)

        await browser.close()

    # Save product URLs
    output_dir = Path(country) / today_date / "Item_urls"
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(str(output_dir / f"{country}_product_urls.json"), purl_list)
    logging.info(f"[COMPLETE] {country}")


def run_country_process(country, config, today_date):
    """Wrapper to run asyncio loop in a separate process."""
    try:
        asyncio.run(process_country(country, config, today_date))
    except Exception as e:
        logging.error(f"[{country}] Process crashed: {e}")


def get_product_data(config_dict, today_date):
    """
    Main function called by Master Code.
    Processes product data for all countries in parallel using multiprocessing.
    """
    logging.info("--- Starting Product Data Extraction ---")
    
    processes = []
    for country, config in config_dict.items():
        p = multiprocessing.Process(target=run_country_process, args=(country, config, today_date))
        p.start()
        processes.append(p)
    
    for p in processes:
        p.join()
        
    logging.info("--- Product Data Extraction Complete ---")
