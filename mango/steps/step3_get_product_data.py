import os
import json
import logging
import time
import shutil
from pathlib import Path
from datetime import date, timedelta
from bs4 import BeautifulSoup
import asyncio
from playwright.async_api import async_playwright

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def save_json(gender, category, name, json_data, date_subfolder):
    try:
        json_dir = date_subfolder / "Json_data" / gender / category
        json_dir.mkdir(parents=True, exist_ok=True)
        with open(json_dir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON for {name}: {e}")

def check_file(gender, category, name, date_subfolder):
    return (date_subfolder / "Json_data" / gender / category / f"{name}.json").exists()

async def log_url_status(log_file, lock, url, status):
    async with lock:
        try:
            current_log = {}
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        current_log = json.load(f)
                except json.JSONDecodeError:
                    current_log = {}
            
            current_log[url] = status
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(current_log, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to update log file {log_file}: {e}")

async def accept_cookies(page):
    try:
        if await page.locator("#cookies\\.button\\.acceptAll").is_visible():
            await page.locator("#cookies\\.button\\.acceptAll").click()
            logging.info("Cookies accepted.")
    except Exception:
        pass

async def accept_country_popup(page):
    try:
        if await page.locator("#changeCountryAccept").is_visible():
            await page.locator("#changeCountryAccept").click()
            logging.info("Country popup accepted.")
    except Exception:
        pass

def extract_json_from_script(content, start_marker, end_marker):
    try:
        start_idx = content.find(start_marker)
        if start_idx == -1:
            return None
        brace_count = 0
        end_idx = start_idx
        for i, char in enumerate(content[start_idx:]):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = start_idx + i + 1
                    break
        if brace_count != 0:
            return None
        json_str = content[start_idx:end_idx]
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

async def process_single_url(page, gender, category, url, date_subfolder):
    name = url.split('/')[-1].replace('?c=', '_').replace('?l=', '_')
    
    # Double check file existence just in case, though re-run logic handles it
    if check_file(gender, category, name, date_subfolder):
        logging.info(f"Skipping already fetched: {name}")
        return 'success'

    try:
        await page.goto(url)
        await page.wait_for_timeout(1000)

        await accept_cookies(page)
        await accept_country_popup(page)

        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script")

        data = {}

        for script in scripts:
            if not script.string:
                continue

            content = script.string.replace("\\", "")

            if 'null,{"product":{"name' in content:
                parsed = extract_json_from_script(content, '{"product":{"name', '}')
                if parsed and 'product' in parsed:
                    data['product'] = parsed.get('product')

            elif '[null,{"type"}],null,{"product":{"name' in content:
                parsed = extract_json_from_script(content, '{"product":{"name', '}')
                if parsed and 'product' in parsed:
                    data['product'] = parsed.get('product')

            elif 'self.__next_f.push([1,"' in content:
                try:
                    start_idx = content.find('self.__next_f.push([1,"') + len('self.__next_f.push([1,"')
                    end_idx = content.rfind('"])')
                    if start_idx != -1 and end_idx != -1:
                        json_str = content[start_idx:end_idx]
                        json_parts = json_str.split('][')
                        for part in json_parts:
                            try:
                                clean_part = part.strip('[]').replace('\n', '')
                                if clean_part.startswith('{') and clean_part.endswith('}'):
                                    parsed = json.loads(clean_part)
                                    if isinstance(parsed, list):
                                        for item in parsed:
                                            if isinstance(item, dict) and 'product' in item:
                                                data['product'] = item.get('product')
                                                break
                                    elif isinstance(parsed, dict) and 'product' in parsed:
                                        data['product'] = parsed.get('product')
                                    if 'product' in data:
                                        break
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    logging.error(f"Error processing __next_f script at {url}: {e}")

            if '"price":{"amount":' in content:
                parsed = extract_json_from_script(content, '{"showAdditionalCurrencies"', '}')
                if parsed:
                    price_info = parsed.get("price", {})
                    crossed_out_prices = parsed.get("crossedOutPrices", [])
                    price_data = {}
                    if price_info:
                        price_data["sale_price"] = {
                            "amount": price_info.get("amount"),
                            "formatted": price_info.get("formatted")
                        }
                    if crossed_out_prices and isinstance(crossed_out_prices, list) and crossed_out_prices[0].get("amount"):
                        price_data["original_price"] = {
                            "amount": crossed_out_prices[0].get("amount"),
                            "formatted": crossed_out_prices[0].get("formatted")
                        }
                    if price_data:
                        data['price'] = price_data

        if data:
            await save_json(gender, category, name, data, date_subfolder)
            return 'success'
        else:
            logging.warning(f"No data found for {url}")
            return 'failure'

    except Exception as e:
        logging.error(f"Error processing {url}: {e}")
        return 'failure'

async def worker(queue, date_subfolder, log_file, lock):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        while True:
            try:
                # Get a "work item" out of the queue.
                task = await queue.get()
                gender, category, url = task
                
                try:
                    status = await process_single_url(page, gender, category, url, date_subfolder)
                    await log_url_status(log_file, lock, url, status)
                except Exception as e:
                    logging.error(f"Worker exception for {url}: {e}")
                    await log_url_status(log_file, lock, url, 'failure')
                finally:
                    # Notify the queue that the "work item" has been processed.
                    queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Worker loop exception: {e}")
        
        await browser.close()

async def monitor_progress(queue, total_urls, start_time, country):
    while True:
        try:
            await asyncio.sleep(10)
            remaining = queue.qsize()
            processed = total_urls - remaining
            elapsed = time.time() - start_time
            
            if processed > 0:
                rate = processed / elapsed # items per second
                eta_seconds = remaining / rate if rate > 0 else 0
                eta_str = str(timedelta(seconds=int(eta_seconds)))
            else:
                eta_str = "Calculating..."
                
            percent = (processed / total_urls) * 100 if total_urls > 0 else 0
            
            logging.info(f"[{country}] Progress: {processed}/{total_urls} ({percent:.2f}%) | Remaining: {remaining} | ETA: {eta_str}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Monitor exception for {country}: {e}")
            break

async def process_country(country, config, today_date, re_run):
    logging.info(f"Starting {country} scraping on {today_date}...")
    
    date_subfolder = Path(country) / today_date
    date_subfolder.mkdir(parents=True, exist_ok=True)
    
    json_data_dir = date_subfolder / "Json_data"
    
    if re_run and json_data_dir.exists():
        logging.info(f"[{country}] re_run=True: Clearing existing data in {json_data_dir}")
        try:
            shutil.rmtree(json_data_dir)
        except Exception as e:
            logging.error(f"[{country}] Failed to clear data directory: {e}")

    # Ensure Json_data directory exists for logs
    json_data_dir.mkdir(parents=True, exist_ok=True)

    # Input file: country/date/Item_urls/country_product_links.json
    file_path = date_subfolder / "Item_urls" / f"{country}_product_links.json"
    
    # Log file: country/date/Json_data/country_product_url_scrap_log.json
    log_file = date_subfolder / "Json_data" / f"{country}_product_url_scrap_log.json"
    
    if not file_path.exists():
        logging.error(f"Product links file not found for {country}: {file_path}")
        return 'failed'

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            urls_dict = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load product links for {country}: {e}")
        return 'failed'

    # Load existing logs for re-run logic
    existing_logs = {}
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                existing_logs = json.load(f)
        except Exception:
            existing_logs = {}

    queue = asyncio.Queue()
    
    total_urls = 0
    queued_urls = 0
    
    for section in urls_dict.values():
        if isinstance(section, dict):
             for category_name, urls in section.items():
                 pass
    
    for gender, subcats in urls_dict.items():
        if isinstance(subcats, dict):
            for category, urls in subcats.items():
                for url in urls:
                    total_urls += 1
                    # Re-run logic
                    if url in existing_logs and existing_logs[url] == 'success':
                        continue
                    
                    queue.put_nowait((gender, category, url))
                    queued_urls += 1
        elif isinstance(subcats, list):
             pass

    logging.info(f"[{country}] Total URLs: {total_urls}, Queued for scraping: {queued_urls}")

    if queued_urls == 0:
        logging.info(f"[{country}] No URLs to scrape.")
        return 'success'

    num_browsers = config.get('browsers_product_data', 1)
    if num_browsers < 1:
        num_browsers = 1
        
    logging.info(f"[{country}] Using {num_browsers} browsers")

    lock = asyncio.Lock()
    workers = []
    
    start_time = time.time()
    
    # Start monitor
    monitor_task = asyncio.create_task(monitor_progress(queue, queued_urls, start_time, country))

    for _ in range(num_browsers):
        workers.append(asyncio.create_task(worker(queue, date_subfolder, log_file, lock)))

    # Wait until the queue is fully processed.
    await queue.join()

    # Cancel our worker tasks.
    for w in workers:
        w.cancel()
    
    # Wait until all worker tasks are cancelled.
    await asyncio.gather(*workers, return_exceptions=True)
    
    # Cancel monitor
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    logging.info(f"{country} scraping finished.")
    return 'success'

async def process_all_countries(config, today_date, re_run):
    tasks = []
    for country, country_config in config.items():
        tasks.append(process_country(country, country_config, today_date, re_run))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    country_statuses = {}
    for country, result in zip(config.keys(), results):
        if isinstance(result, Exception):
             logging.error(f"Error in {country}: {result}")
             country_statuses[country] = 'failed'
        else:
             country_statuses[country] = result
    return country_statuses

def get_product_data(config, today_date, re_run=False):
    """
    Main entry point for Step 3.
    Args:
        config (dict): Configuration dictionary containing country settings.
        today_date (str): Date string (YYYY-MM-DD).
        re_run (bool): Whether to re-run scraping (handled internally by log check).
    Returns:
        dict: Status for each country {'CountryName': 'success'/'failed'}
    """
    return asyncio.run(process_all_countries(config, today_date, re_run))
