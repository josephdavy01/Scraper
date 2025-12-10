import json
import asyncio
import logging
import multiprocessing
import os
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

# ----------------------------------------------------------------------
# Configure logging
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ----------------------------------------------------------------------
# Helper: Accept cookies popup
# ----------------------------------------------------------------------
async def accept_cookies(page):
    try:
        await page.wait_for_selector("#cookies\\.button\\.acceptAll", timeout=5000)
        await page.click("#cookies\\.button\\.acceptAll")
        logging.info("Cookies accepted.")
        return True
    except Exception:
        # logging.info(f"Cookies popup not found or already accepted.")
        return False

# ----------------------------------------------------------------------
# Helper: Accept country selection popup
# ----------------------------------------------------------------------
async def accept_country_popup(page):
    try:
        await page.wait_for_selector("#changeCountryAccept", timeout=5000)
        await page.click("#changeCountryAccept")
        logging.info("Country selection accepted.")
        return True
    except Exception:
        # logging.info(f"Country popup not found or already accepted.")
        return False

# ----------------------------------------------------------------------
# Helper: Auto-scroll to load dynamic content
# ----------------------------------------------------------------------
async def auto_scroll(page):
    logging.info("Starting slow scroll...")
    await page.evaluate("""
        async () => {
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
            let lastHeight = document.body.scrollHeight;
            let noChangeCount = 0;
            const maxAttempts = 15;
            while (noChangeCount < maxAttempts) {
                window.scrollBy(0, 300);
                await delay(500);
                let newHeight = document.body.scrollHeight;
                if (newHeight === lastHeight) {
                    noChangeCount++;
                } else {
                    noChangeCount = 0;
                    lastHeight = newHeight;
                }
            }
        }
    """)
    logging.info("Finished scrolling.")

# ----------------------------------------------------------------------
# Core: Extract product URLs from a category page
# ----------------------------------------------------------------------
async def get_urls(page, url, cookies_status, country_popup_status, exclude_urls=None, retries=3):
    # 🚫 Safety net: never scrape excluded URLs
    if exclude_urls and url in exclude_urls:
        logging.info(f"Skipping excluded URL inside get_urls: {url}")
        return [], cookies_status, country_popup_status

    for attempt in range(retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            break
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt == retries - 1:
                return [], cookies_status, country_popup_status
            await asyncio.sleep(2)

    # Accept popups only once per browser session
    if not cookies_status:
        cookies_status = await accept_cookies(page)
    if not country_popup_status:
        country_popup_status = await accept_country_popup(page)

    # Wait for product grid (optional)
    try:
        await page.wait_for_selector("a.ProductImage_imageWrapper__JfhWa", timeout=10000)
    except Exception:
        logging.warning("Product grid not detected, still proceeding with scrape.")

    await auto_scroll(page)

    # Try multiple possible selectors
    selectors = [
        "div.virtual-list a.ProductImage_imageWrapper__JfhWa",
        "div[data-slot] a.ProductImage_imageWrapper__JfhWa",
        "a.ProductImage_imageWrapper__JfhWa"
    ]
    urls = []
    for selector in selectors:
        try:
            elements = await page.query_selector_all(selector)
            for element in elements:
                href = await element.get_attribute("href")
                if href:
                    abs_url = urljoin(url, href)
                    if abs_url not in urls:
                        urls.append(abs_url)
            if urls:
                break
        except Exception as e:
            logging.warning(f"No elements found for selector {selector}: {e}")

    logging.info(f"Found {len(urls)} product URLs for {url}")
    return urls, cookies_status, country_popup_status

# ----------------------------------------------------------------------
# Worker Process: Consumes URLs from Queue
# ----------------------------------------------------------------------
async def worker_process(queue, output_file, log_file, country, file_lock, exclude_urls, proxies=None):
    cookies_status = False
    country_popup_status = False

    async with async_playwright() as p:
        # Configure browser launch options
        launch_options = {"headless": False}
        if proxies:
            launch_options["proxy"] = {
                "server": proxies["server"],
                "username": proxies["username"],
                "password": proxies["password"]
            }
        
        browser = await p.chromium.launch(**launch_options)
        context = await browser.new_context()

        # Block images, fonts, and media to save bandwidth/speed
        async def block_resources(route):
            req = route.request
            blocked_types = ["image", "media", "font"]
            blocked_exts = [".jpg", ".jpeg", ".png", ".gif", ".svg", ".mp4", ".woff", ".ttf"]
            if req.resource_type in blocked_types or any(ext in req.url.lower() for ext in blocked_exts):
                await route.abort()
            else:
                await route.continue_()
        await context.route("**/*", block_resources)

        page = await context.new_page()

        while True:
            try:
                # Get item from queue
                item = queue.get_nowait()
            except Exception:
                # Queue is empty, but we should rely on sentinel for clean exit usually.
                # If using get_nowait, we might exit early if queue is temporarily empty but writers are active.
                # However, here the main process fills the queue before starting workers.
                break
            
            if item is None:
                # Sentinel received, exit loop
                break

            category_name, url = item

            # Skip excluded URLs
            if url in exclude_urls:
                logging.info(f"Skipping excluded URL: {url}")
                continue

            # Build human-readable subcategory name
            path_parts = urlparse(url).path.strip("/").split("/")
            if len(path_parts) >= 1:
                subcategory_raw = path_parts[-1].split("_")[0]
                subcategory_parent = path_parts[-2] if len(path_parts) > 1 else ""
                subcategory = f"{subcategory_parent}-{subcategory_raw}".replace("-", " ").title()
            else:
                subcategory = "Unknown"

            # Check if already scraped using the log file
            already_done = False
            with file_lock:
                if Path(log_file).exists() and Path(log_file).stat().st_size > 0:
                    try:
                        with open(log_file, "r", encoding="utf-8") as f:
                            log_data = json.load(f)
                            if isinstance(log_data, list):
                                already_done = any(
                                    e.get("category_name") == category_name and e.get("subcategory") == subcategory and e.get("status") == "success"
                                    for e in log_data
                                )
                    except json.JSONDecodeError:
                        pass
            
            if already_done:
                logging.info(f"Skipping already scraped: {category_name} → {subcategory}")
                continue

            logging.info(f"Fetching URLs for {category_name} → {subcategory}")

            # Perform the scrape
            urls, cookies_status, country_popup_status = await get_urls(
                page, url, cookies_status, country_popup_status, exclude_urls=exclude_urls
            )

            # Update Data File
            with file_lock:
                data = {}
                if Path(output_file).exists() and Path(output_file).stat().st_size > 0:
                    try:
                        with open(output_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if not isinstance(data, dict):
                            logging.warning(f"Existing data in {output_file} is not a dict, starting fresh.")
                            data = {}
                    except json.JSONDecodeError:
                        logging.warning(f"Corrupted JSON in {output_file}, starting fresh.")
                        data = {}
                
                if category_name not in data:
                    data[category_name] = {}
                
                if subcategory in data[category_name]:
                        # Avoid duplicates if extending
                        existing_urls = set(data[category_name][subcategory])
                        existing_urls.update(urls)
                        data[category_name][subcategory] = list(existing_urls)
                else:
                    data[category_name][subcategory] = urls

                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)

            # Update Log File
            log_entry = {
                "category_name": category_name,
                "subcategory": subcategory,
                "url": url,
                "status": "success",
                "count": len(urls),
                "timestamp": datetime.now().isoformat()
            }

            with file_lock:
                logs = []
                if Path(log_file).exists() and Path(log_file).stat().st_size > 0:
                    try:
                        with open(log_file, "r", encoding="utf-8") as f:
                            logs = json.load(f)
                        if not isinstance(logs, list):
                            logs = []
                    except json.JSONDecodeError:
                        logs = []
                
                logs.append(log_entry)
                with open(log_file, "w", encoding="utf-8") as f:
                    json.dump(logs, f, ensure_ascii=False, indent=4)

            logging.info(f"Saved {len(urls)} URLs for {category_name} → {subcategory}")

        await browser.close()

# ----------------------------------------------------------------------
# Process wrapper
# ----------------------------------------------------------------------
def run_worker_process(queue, output_file, log_file, country, file_lock, exclude_urls, proxies):
    asyncio.run(worker_process(queue, output_file, log_file, country, file_lock, exclude_urls, proxies))

# ----------------------------------------------------------------------
# Main entry point called by master_v1.py
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# Process wrapper for country
# ----------------------------------------------------------------------
def process_country(country, country_config, date_str, re_run):
    logging.info(f"Starting product URL scraping for {country}...")
    
    # Setup paths
    input_file = os.path.join(country, date_str, "Category", f"{country}_category.json")
    output_dir = Path(f'{country}/{date_str}/Item_urls')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    final_output_file = output_dir / f"{country}_product_links.json"
    log_file = output_dir / f"{country}_product_urls_scrap_log.json"

    # Check input file
    if not Path(input_file).exists():
        logging.error(f"Input file not found for {country}: {input_file}")
        return

    # Initialize files if they don't exist or if re_run is requested
    if re_run:
        if final_output_file.exists():
            final_output_file.unlink()
        if log_file.exists():
            log_file.unlink()
    
    if not final_output_file.exists():
        final_output_file.write_text("{}", encoding="utf-8")
    
    if not log_file.exists():
        log_file.write_text("[]", encoding="utf-8")

    # Load categories
    try:
        with open(input_file, encoding="utf-8") as f:
            url_dict = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load category links for {country}: {e}")
        return

    # Get exclude URLs from config
    exclude_urls = set(country_config.get('exclude_urls', []))
    
    # Filter URLs
    filtered_url_dict = {}
    for category, urls in url_dict.items():
        filtered_urls = [u for u in urls if u not in exclude_urls]
        if filtered_urls:
            filtered_url_dict[category] = filtered_urls
        
        before = len(urls)
        after = len(filtered_urls)
        if before != after:
            logging.info(f"Excluded {before - after} URLs from {category} in {country}")

    if not filtered_url_dict:
        logging.warning(f"No URLs to scrape for {country} after filtering.")
        return

    # Determine number of browsers
    num_browsers = country_config.get('browsers_product_urls', 1)
    
    # Multiprocessing setup
    manager = multiprocessing.Manager()
    file_lock = manager.Lock()
    queue = manager.Queue()
    
    # Enqueue all items
    for cat, urls in filtered_url_dict.items():
        for url in urls:
            queue.put((cat, url))
    
    # Add sentinels
    for _ in range(num_browsers):
        queue.put(None)

    proxies = country_config.get('proxies') if country_config.get('use_proxies') else None

    processes = []
    for _ in range(num_browsers):
        p = multiprocessing.Process(
            target=run_worker_process,
            args=(queue, str(final_output_file), str(log_file), country, file_lock, exclude_urls, proxies)
        )
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    logging.info(f"Completed product URL scraping for {country}.")

# ----------------------------------------------------------------------
# Main entry point called by master_v1.py
# ----------------------------------------------------------------------
def get_product_urls(config, date_str, re_run=False):
    """
    Main function to get product URLs for all countries in the config.
    Spawns a process for each country to run in parallel.
    """
    processes = []
    for country, country_config in config.items():
        p = multiprocessing.Process(
            target=process_country,
            args=(country, country_config, date_str, re_run)
        )
        p.start()
        processes.append(p)
    
    for p in processes:
        p.join()
