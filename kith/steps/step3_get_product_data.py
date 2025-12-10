import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from tqdm.asyncio import tqdm
import random

NUM_BROWSERS_PER_COUNTRY = 2 # Default fallback

# --- Helper functions ---

def load_log(log_path):
    """Loads a JSON log file, returning an empty dict if it doesn't exist or is invalid."""
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_log(log_path, log_data):
    """Saves a dictionary to a JSON log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)

def extract_handle(url):
    """Extracts the product handle from a URL."""
    return url.rstrip("/").split("/")[-1]

def build_url_to_path_map(data, path=None):
    """Recursively builds a map from URL to its category path."""
    if path is None:
        path = []
    url_map = {}
    if isinstance(data, dict):
        for key, value in data.items():
            url_map.update(build_url_to_path_map(value, path + [key]))
    elif isinstance(data, list):
        for url in data:
            url_map[url] = path
    return url_map

async def close_popups(page, config):
    """Clicks on known popup selectors to close them."""
    selectors = [
        config.get('welcome_mat_selector'),
        *config.get('popup_selectors', [])
    ]
    for selector in selectors:
        if not selector:
            continue
        try:
            await page.locator(selector).click(timeout=7000)
            print(f"Closed popup with selector: {selector}")
        except Exception:
            pass # Popup may not be present

async def set_country(page, country, country_config):
    """Sets the country/currency on the website and verifies the change, with retries."""
    base_url = country_config['base_url']
    currency_code = ""
    if country == 'USA': currency_code = 'US'
    elif country == 'UK': currency_code = 'GB'
    
    if not currency_code:
        print(f"Warning: No currency code configured for country {country}")
        return False

    max_retries = 3
    for attempt in range(max_retries):
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
            print(f"Landed on {base_url}. Waiting for popups...")
            await page.wait_for_timeout(random.uniform(5000, 8000)) # Increased wait time

            await close_popups(page, country_config)
            
            # After popups, wait for any potential page refresh to complete.
            print("Waiting for page to settle after closing popups...")
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            await asyncio.sleep(2)

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)
            
            selector = "select#currencySwitch-footer-desktop"
            print(f"Attempting to change currency... (Attempt {attempt + 1}/{max_retries})")
            await page.wait_for_selector(selector, timeout=15000, state='visible')

            current_value = await page.locator(selector).input_value()
            if current_value.upper() == currency_code:
                print(f"Country already correctly set to {country} ({currency_code}).")
                return True

            # Perform the currency change and wait for the resulting navigation
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
                await page.select_option(selector, value=currency_code)
            
            print("Page reloaded, verifying currency...")
            await page.wait_for_timeout(random.uniform(2000, 4000))

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_selector(selector, timeout=15000, state='visible')

            new_value = await page.locator(selector).input_value()
            if new_value.upper() == currency_code:
                print(f"Successfully verified currency change to {country} ({currency_code}).")
                return True
            else:
                print(f"Failed to verify currency change on attempt {attempt + 1}. Expected {currency_code}, but found {new_value}.")
                
        except Exception as e:
            print(f"Could not set country to {country} on attempt {attempt + 1}. An error occurred: {e}")
        
        if attempt < max_retries - 1:
            print("Retrying country setup...")
            await asyncio.sleep(random.uniform(3, 5))

    print(f"Failed to set country to {country} after {max_retries} attempts.")
    return False


async def extract_product_data_from_page(page):
    """Extracts the ProductJSON and LD+JSON data from the product page."""
    product_json_data = None
    ld_json_data = None
    try:
        json_element = await page.query_selector('script#ProductJSON')
        if json_element:
            product_json_data = json.loads(await json_element.inner_text())

        ld_elements = await page.query_selector_all('script[type="application/ld+json"]')
        for element in ld_elements:
            ld_data = json.loads(await element.inner_text())
            if isinstance(ld_data, list): # Some pages have a list of ld+json objects
                for item in ld_data:
                    if isinstance(item, dict) and item.get('@type') == 'Product':
                        ld_json_data = item
                        break
            elif isinstance(ld_data, dict) and ld_data.get('@type') == 'Product':
                ld_json_data = ld_data
                break
            if ld_json_data:
                break
    except Exception as e:
        print(f"Error parsing JSON on page {page.url}: {e}")

    return {
        "product_json": product_json_data,
        "ld_json": ld_json_data
    } if product_json_data else None


async def worker(country, country_config, work_queue, log, log_path, data_path, progress, country_setup_failed_event):
    """A worker process that launches a browser and scrapes URLs from the queue."""
    use_proxies = country_config.get('use_proxies_product', False)
    proxy_config = country_config.get('proxies') if use_proxies else None
    
    playwright_proxy = None
    if proxy_config:
        playwright_proxy = { "server": proxy_config["server"] }
        
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            proxy=playwright_proxy,
            args=[
                '--disable-infobars',
                '--disable-blink-features=AutomationControlled',
                '--disable-popup-blocking'
            ]
        )
        
        context_args = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        }
        if proxy_config and proxy_config.get("username"):
            context_args["http_credentials"] = {
                "username": proxy_config["username"],
                "password": proxy_config["password"]
            }

        context = await browser.new_context(**context_args)
        page = await context.new_page()

        if not await set_country(page, country, country_config):
            print(f"[{country}] Worker failed to initialize country settings. Aborting this worker.")
            country_setup_failed_event.set()
            await browser.close()
            # Drain the queue for this country's progress bar
            while not work_queue.empty():
                work_queue.get_nowait()
                progress.update(1)
            return

        while not work_queue.empty():
            if country_setup_failed_event.is_set():
                print(f"[{country}] Aborting due to setup failure in another worker.")
                break

            url, path_list = await work_queue.get()
            handle = extract_handle(url)
            
            # Create subdirectory structure
            output_dir = data_path.joinpath(*path_list)
            output_dir.mkdir(parents=True, exist_ok=True)
            out_file = output_dir / f"{handle}.json"
            
            if out_file.exists():
                progress.update(1)
                work_queue.task_done()
                continue
            
            max_retries = 3
            success = False
            for attempt in range(max_retries):
                try:
                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    
                    is_404 = await page.locator("h1:has-text('Page not found')").is_visible(timeout=2000)
                    if is_404:
                        print(f"[{country}] Page not found for {url}. Skipping.")
                        log[url] = {"status": "failed", "reason": "Page not found (404)"}
                        success = True # Mark as handled to prevent generic failure message
                        break

                    await close_popups(page, country_config)
                    
                    await page.wait_for_selector('script#ProductJSON', timeout=20000, state='attached')
                    
                    data = await extract_product_data_from_page(page)
                    
                    if data and data.get('product_json'):
                        with open(out_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        log[url] = {"status": "done"}
                    else:
                        log[url] = {"status": "failed", "reason": "No data extracted"}
                    
                    success = True
                    break
                except Exception as e:
                    print(f"[{country}] Attempt {attempt + 1}/{max_retries} failed for {url}: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(random.uniform(3, 5))
            
            if not success:
                log[url] = {"status": "failed", "reason": f"Failed after {max_retries} retries"}

            save_log(log_path, log)
            progress.update(1)
            work_queue.task_done()

        await page.close()
        await context.close()
        await browser.close()


def get_product_data(config, date_str):
    """Main function to orchestrate the scraping of product data for all countries."""
    
    country_statuses = {}
    pop_keys = ['jb', 'nb', 'tb', 'hn', 'dm', 'ug', 'nk', 'aa', 'cd', 'ves', 'pu']
    def should_skip(url):
        handle = extract_handle(url).lower()
        return any(handle.startswith(key) for key in pop_keys)

    async def run_for_country(country, country_config):
        country_setup_failed_event = asyncio.Event()
        item_file = Path(country) / date_str / "Item_urls" / f"{country}_product_links.json"
        data_path = Path(country) / date_str / "Json_data"
        data_path.mkdir(parents=True, exist_ok=True)
        log_path = data_path / f"{country}_scrape_log.json"
        log = load_log(log_path)

        if not item_file.exists():
            print(f"Item URL file not found for {country}, skipping.")
            country_statuses[country] = 'skipped'
            return

        with open(item_file, 'r', encoding='utf-8') as f:
            url_data = json.load(f)

        url_to_path = build_url_to_path_map(url_data)

        pending_items = []
        for url, path in url_to_path.items():
            if should_skip(url):
                continue

            log_entry = log.get(url, {})
            if log_entry.get("status") == "done":
                continue
            
            if log_entry.get("reason") == "Page not found (404)":
                continue
            
            pending_items.append((url, path))
        
        if not pending_items:
            print(f"No new product data to scrape for {country}.")
            country_statuses[country] = 'success'
            return

        work_queue = asyncio.Queue()
        for item in pending_items:
            work_queue.put_nowait(item)

        pbar = tqdm(total=len(pending_items), desc=f"[{country}] Scraping Data", position=0, leave=True)
        
        num_browsers = country_config.get('browsers', NUM_BROWSERS_PER_COUNTRY)
        print(f"-> Starting {num_browsers} browser(s) for {country}...")

        tasks = [
            worker(country, country_config, work_queue, log, log_path, data_path, pbar, country_setup_failed_event)
            for _ in range(num_browsers)
        ]
        await asyncio.gather(*tasks)
        pbar.close()

        if country_setup_failed_event.is_set():
            country_statuses[country] = 'failed'
        else:
            country_statuses[country] = 'success'

    async def main_run():
        country_tasks = [run_for_country(c, conf) for c, conf in config.items()]
        await asyncio.gather(*country_tasks)
    
    asyncio.run(main_run())

    return country_statuses