import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

# Constants from step3
NUM_BROWSERS_PER_COUNTRY = 2
SCROLL_DELAY = 300
SCROLL_ATTEMPTS = 30

# Selectors from step3
COLLECTION_GRID_SELECTOR = "ul[js-products-grid] li a"
SUBCOLLECTION_GRID_SELECTOR = "ul[js-subcollection-products] li a"

# --- Helper functions ---

def load_log(log_path):
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_log(log_path, log_data):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)

async def update_results_json(out_path, path, product_urls, file_lock):
    """Safely updates the nested JSON output file."""
    async with file_lock:
        data = {}
        if out_path.exists() and out_path.stat().st_size > 0:
            with open(out_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}
        
        d = data
        for key in path[:-1]:
            d = d.setdefault(key, {})
        
        d[path[-1]] = product_urls

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

async def write_log(log_path, log, file_lock):
    async with file_lock:
        save_log(log_path, log)

async def close_popups(page, config):
    selectors = [
        config.get('welcome_mat_selector'),
        *config.get('popup_selectors', [])
    ]
    for selector in selectors:
        if not selector: continue
        try:
            await page.locator(selector).click(timeout=5000)
            print(f"Closed popup: {selector}")
        except Exception:
            pass

async def scroll_to_bottom(page):
    for _ in range(SCROLL_ATTEMPTS):
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await page.wait_for_timeout(SCROLL_DELAY)

async def extract_product_urls_from_page(page):
    product_urls = set()
    anchors = await page.query_selector_all(COLLECTION_GRID_SELECTOR)
    for a in anchors:
        href = await a.get_attribute("href")
        if href and "/products/" in href:
            product_urls.add("https://" + page.url.split("/")[2] + href)

    if not product_urls:
        anchors = await page.query_selector_all(SUBCOLLECTION_GRID_SELECTOR)
        for a in anchors:
            href = await a.get_attribute("href")
            if href and "/products/" in href:
                product_urls.add("https://" + page.url.split("/")[2] + href)

    return list(product_urls)

async def extract_urls_from_collection(page, url, country_config):
    try:
        await page.goto(url, timeout=600000)
        await page.wait_for_load_state("domcontentloaded")
        await close_popups(page, country_config)

        no_products_selector = "div.p-sm.desktop\\:p-md span.h3"
        no_products_elem = await page.query_selector(no_products_selector)
        if no_products_elem:
            text = await no_products_elem.inner_text()
            if "No Products Found" in text:
                print(f"No products found at {url}")
                return "no_products"

        toggle_selector = "button[js-toggle-grid]"
        toggle = await page.query_selector(toggle_selector)
        if toggle:
            await toggle.click()
            await page.wait_for_timeout(500)

        await scroll_to_bottom(page)
        return await extract_product_urls_from_page(page)

    except Exception as e:
        print(f"Failed to scrape {url}: {str(e)}")
        return []

async def worker(country, country_config, work_queue, log, log_path, out_path, file_lock):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        while not work_queue.empty():
            path, url = await work_queue.get()
            print(f"[{country}] Scraping: {url} for category {' -> '.join(path)}")

            product_urls = await extract_urls_from_collection(page, url, country_config)

            if product_urls == "no_products":
                await update_results_json(out_path, path, [], file_lock)
                log[url] = {"count": 0, "status": "done"}
            elif product_urls:
                await update_results_json(out_path, path, product_urls, file_lock)
                log[url] = {"count": len(product_urls), "status": "done"}
            else:
                log[url] = {"count": 0, "status": "failed"}

            await write_log(log_path, log, file_lock)
            work_queue.task_done()

        await page.close()
        await browser.close()

def get_product_urls(config, date_str, re_run=False):
    async def run():
        country_tasks = []
        for country, country_config in config.items():
            cat_file = Path(country) / date_str / "Category" / f"{country}_category_links.json"
            output_dir = Path(country) / date_str / "Item_urls"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{country}_product_links.json"
            log_path = output_dir / f"{country}_scrape_log.json"

            if re_run:
                if output_file.exists(): output_file.unlink()
                if log_path.exists(): log_path.unlink()

            if not cat_file.exists():
                print(f"Category file not found for {country}, skipping: {cat_file}")
                continue
            
            with open(cat_file, 'r', encoding='utf-8') as f:
                raw_cat_data = json.load(f)
            
            log_data = load_log(log_path)
            work_queue = asyncio.Queue()

            def build_work_queue(data, path_prefix=[]):
                if isinstance(data, dict):
                    for key, value in data.items():
                        current_path = path_prefix + [key]
                        if isinstance(value, str) and value.startswith('http'):
                            url = value
                            if country_config['domain'] in url:
                                if re_run or log_data.get(url, {}).get("status") != "done":
                                    work_queue.put_nowait((current_path, url))
                        else:
                            build_work_queue(value, current_path)
                elif isinstance(data, list):
                    for item in data:
                        build_work_queue(item, path_prefix)
            
            build_work_queue(raw_cat_data)

            if work_queue.empty():
                print(f"No new product URLs to scrape for {country}.")
                continue

            if not output_file.exists() or output_file.stat().st_size == 0:
                with open(output_file, 'w') as f: json.dump({}, f)
            
            file_lock = asyncio.Lock()
            
            tasks = [
                worker(country, country_config, work_queue, log_data, log_path, output_file, file_lock)
                for _ in range(country_config.get('browsers', NUM_BROWSERS_PER_COUNTRY))
            ]
            country_tasks.append(asyncio.gather(*tasks))

        if country_tasks:
            await asyncio.gather(*country_tasks)

    asyncio.run(run())