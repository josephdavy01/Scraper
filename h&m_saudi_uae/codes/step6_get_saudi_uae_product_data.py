import os
import json
import logging
import asyncio
import random
from pathlib import Path
from datetime import date, datetime, timedelta
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
# from proxy_list import PROXY_LIST
from collections import defaultdict
import time
from datetime import timedelta

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/saudi_uae_product_data.log', mode='a'),
    ]
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

COUNTRY_CONFIG = {
    'Saudi': {
        'base': 'https://sa.hm.com',
        # 'proxies': PROXY_LIST.copy(),
        'genders': ['Men', 'Women', 'Kids', 'Baby']
    },
    'UAE': {
        'base': 'https://ae.hm.com',
        # 'proxies': PROXY_LIST.copy(),
        'genders': ['Men', 'Women', 'Kids', 'Baby']
    }
}

progress = defaultdict(lambda: {'total': 0, 'done': 0})
print_lock = asyncio.Lock()

def get_logger(log_path):
    logger = logging.getLogger(log_path)
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, mode='a')
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    fh.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(fh)
    return logger

async def update_progress(country):
    async with print_lock:
        p = progress[country]
        now = time.time()

        # Start timer
        if p['start_time'] is None:
            p['start_time'] = now
            elapsed = 0
        else:
            elapsed = now - p['start_time']

        # Calculate rate (items per second)
        p['rate'] = p['done'] / elapsed if elapsed > 0 else 0

        # ETA calculation
        eta = "Calculating..."
        if p['rate'] > 0 and p['done'] < p['total']:
            remaining = p['total'] - p['done']
            eta_seconds = int(remaining / p['rate'])
            eta = str(timedelta(seconds=eta_seconds)).rjust(8)

        # Progress bar
        percent = (p['done'] / p['total']) * 100 if p['total'] > 0 else 0
        bar_length = 20
        filled_length = int(bar_length * percent / 100)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)

        # Format line
        line = f"{country.ljust(6)}: {p['done']:4d}/{p['total']:4d} [{bar}] {percent:5.1f}% ETA: {eta}"
        print(f"\r{line.ljust(80)}", end='', flush=True)

        if p['done'] == p['total']:
            print()  # New line when done

async def save_json(gender, pid, json_data, date_folder):
    path = date_folder / 'Json_data' / gender
    path.mkdir(parents=True, exist_ok=True)
    with open(path / f'{pid}.json', 'w') as f:
        json.dump(json_data, f, indent=4)

def check_file(gender, pid, date_folder):
    return (date_folder / 'Json_data' / gender / f'{pid}.json').exists()

class CountryScraper:
    def __init__(self, country, playwright, proxy_pool):
        self.country = country
        self.base_url = COUNTRY_CONFIG[country]['base']
        self.playwright = playwright
        self.proxy_pool = proxy_pool
        self.proxy_index = 0
        self.browser = None
        self.context = None
        self.page = None

    def get_next_proxy(self):
        proxy = self.proxy_pool[self.proxy_index % len(self.proxy_pool)]
        self.proxy_index += 1
        return proxy

    async def recreate_browser(self):
        await self.close()
        # host, port, user, pwd = self.get_next_proxy().split(":")
        # proxy_settings = {
        #     "server": f"http://{host}:{port}",
        #     "username": user,
        #     "password": pwd
        # }
        # self.browser = await self.playwright.chromium.launch(proxy=proxy_settings, headless=False)
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context(user_agent=random.choice(USER_AGENTS))
        self.page = await self.context.new_page()

    async def close(self):
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def ensure_browser(self):
        if not self.browser:
            await self.recreate_browser()

    async def process_url(self, gender, pid, date_folder, failed_log):
        # Use pid directly if it's a full URL
        url = pid if pid.startswith("http") else f"{self.base_url}/en/{pid}"

        if check_file(gender, pid.split("/")[-1], date_folder):
            progress[self.country]['done'] += 1
            return

        for attempt in range(3):
            try:
                await self.ensure_browser()
                await self.page.goto(url, timeout=30000)

                # Wait for all necessary elements to load
                await self.page.wait_for_selector("script[data-name='product']", state="attached", timeout=10000)
                await self.page.wait_for_selector("script[data-name='breadcrumb']", state="attached", timeout=10000)
                await self.page.wait_for_selector(".pdp-product__prices", state="attached", timeout=10000)
                await self.page.wait_for_selector(".pdp-swatches__title", state="attached", timeout=10000)
                await self.page.wait_for_selector(".pdp-swatches__options", state="attached", timeout=10000)
                await self.page.wait_for_selector(".pdp-product-description__attributes", state="attached", timeout=10000)


                # Parse content
                html = await self.page.content()
                soup = BeautifulSoup(html, "html.parser")
                json_data = {}

                # Product
                product_tag = soup.find("script", {"type": "application/ld+json", "data-name": "product"})
                if not product_tag or not product_tag.get_text(strip=True):
                    raise Exception("Missing or empty product JSON script")
                product = json.loads(product_tag.get_text(strip=True))

                # Price Range
                price = {}
                price_main = soup.find("div", {"class": "pdp-product__prices"})
                if price_main:
                    for div in price_main.find_all("div", {"role": "text"}):
                        key = div.get("data-slot", "").lower()
                        span = div.find("span")
                        if key and span:
                            value = span.text.strip().split('\xa0')[-1].replace(",", "")
                            price[key] = value

                # Color
                color_tag = soup.find("p", {"class": "pdp-swatches__title"})
                color = color_tag.text.strip() if color_tag else ""

                # Sizes
                sizes = {}
                for size_tag in soup.select("div.pdp-swatches__options input"):
                    label = size_tag.get("aria-label", "").strip().lower()
                    size = size_tag.get("value", "").strip()
                    if size:
                        sizes[size] = 'out_of_stock' if 'out of stock' in label else 'in_stock'

                # Attributes
                attributes = {}
                for ul in soup.select("div.pdp-product-description__attributes ul"):
                    label_div = ul.find("div")
                    value_span = ul.find("span")
                    if label_div and value_span:
                        attributes[label_div.text.strip()] = value_span.text.strip()

                # Breadcrumb
                breadcrumb_tag = soup.find("script", {"type": "application/ld+json", "data-name": "breadcrumb"})
                breadcrumb = json.loads(breadcrumb_tag.get_text(strip=True)) if breadcrumb_tag else {}

                # Build and save JSON
                json_data = {
                    "product": product,
                    "price": price,
                    "color": color,
                    "sizes": sizes,
                    "attributes": attributes,
                    "breadcrumb": breadcrumb
                }

                filename = pid.split("/")[-1]
                await save_json(gender, filename, json_data, date_folder)
                progress[self.country]['done'] += 1
                await update_progress(self.country)
                return

            except Exception as e:
                failed_log.error(f"{self.country} - Failed for {url}: {e}")
                await self.recreate_browser()

        progress[self.country]['done'] += 1
        await update_progress(self.country)


async def scrape_country(country, playwright):
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-08'
    data_folder = Path(country) / "Data" / today_str
    item_path = data_folder / "Item_urls" / f"{country}_unique_product_urls.json"
    log_dir = Path(country) / "Logs" / today_str
    log_dir.mkdir(parents=True, exist_ok=True)
    failed_log = get_logger(str(log_dir / "failed_urls.log"))

    with open(item_path) as f:
        product_urls = json.load(f)

    genders = COUNTRY_CONFIG[country]['genders']
    all_tasks = [(g, pid) for g in genders if g in product_urls for pid in product_urls[g]]
    progress[country] = {
    'total': len(all_tasks),
    'done': 0,
    'start_time': None,
    'last_update': 0,
    'rate': 0
}

    progress[country]['done'] = 0

    task_queue = asyncio.Queue()
    for item in all_tasks:
        gender, pid = item
        if not check_file(gender, pid, data_folder):
            task_queue.put_nowait(item)

    if task_queue.empty():
        print(f"{country} - All products already processed.")
        return

    proxy_pool = []
    # proxy_pool = COUNTRY_CONFIG[country]['proxies']
    # random.shuffle(proxy_pool)

    async def worker(worker_id):
        scraper = CountryScraper(country, playwright, proxy_pool)
        while not task_queue.empty():
            gender, pid = await task_queue.get()
            await scraper.process_url(gender, pid, data_folder, failed_log)
            task_queue.task_done()
        await scraper.close()

    workers = [asyncio.create_task(worker(i)) for i in range(4)]
    await asyncio.gather(*workers)
    print(f"{country} - Completed {progress[country]['done']}/{progress[country]['total']}")

async def main():
    async with async_playwright() as playwright:
        await asyncio.gather(
            scrape_country("Saudi", playwright),
            scrape_country("UAE", playwright)
        )

if __name__ == "__main__":
    asyncio.run(main())
