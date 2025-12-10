import os
import json
import logging
import asyncio
import random
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from collections import defaultdict

PROXIES = {
    "India": {
        "server": "p.webshare.io:80",
        "username": "wyrmemzp-rotate",
        "password": "pg2iw8gey30z"
    },
    "UK": {
        "server": "p.webshare.io:80",
        "username": "wyrmemzp-rotate",
        "password": "pg2iw8gey30z"
    }
}

PROXY_POOL = {
    'India': [PROXIES['India']],
    'UK': [PROXIES['UK']]
}

COUNTRY_ENDPOINTS = {
    "India": "in",
    "UK": "gb"
}

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/product_data_scraper.log', mode='a'),
    ]
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

COUNTRY_CONFIG = {
    'India': {
        'domain': 'en_in',
        'proxies': PROXY_POOL['India'].copy(),
        'genders': ['baby', 'kids', 'women', 'men']
    },
    'UK': {
        'domain': 'en_gb',
        'proxies': PROXY_POOL['UK'].copy(),
        'genders': ['kids', 'men', 'women']
    }
}

progress = defaultdict(lambda: {
    'total': 0,
    'done': 0,
    'start_time': None,
    'last_update': 0,
    'rate': 0
})
print_lock = asyncio.Lock()
TERMINAL_WIDTH = 80

def get_logger(log_path):
    logger = logging.getLogger(log_path)
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, mode='a')
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    fh.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(fh)
    return logger

async def save_json(gender, pid, json_data, date_subfolder):
    try:
        json_file_path = date_subfolder / 'Json_data' / gender
        json_file_path.mkdir(parents=True, exist_ok=True)
        with open(json_file_path / f'{pid}.json', 'w') as outfile:
            json.dump(json_data, outfile, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON for {pid}: {e}")

def check_file(gender, pid, date_subfolder):
    return os.path.exists(f'{date_subfolder}/Json_data/{gender}/{pid}.json')

def format_timedelta(td):
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

async def update_progress(country):
    async with print_lock:
        p = progress[country]
        now = time.time()
        if p['start_time'] is None:
            p['start_time'] = now
            elapsed = 0
        else:
            elapsed = now - p['start_time']
        if elapsed > 0:
            p['rate'] = p['done'] / elapsed
        eta = "Calculating..."
        if p['rate'] > 0 and p['done'] > 0:
            remaining = p['total'] - p['done']
            eta_seconds = remaining / p['rate']
            eta = format_timedelta(timedelta(seconds=eta_seconds))
        percent = (p['done'] / p['total']) * 100 if p['total'] > 0 else 0
        bar_length = 20
        filled_length = int(bar_length * percent / 100)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        progress_line = (
            f"{country.ljust(6)}: "
            f"{p['done']:4d}/{p['total']:4d} "
            f"[{bar}] {percent:5.1f}% "
            f"ETA: {eta}"
        )
        if now - p['last_update'] > 0.5 or p['done'] == p['total']:
            print(f"\r{progress_line.ljust(TERMINAL_WIDTH)}", end='', flush=True)
            p['last_update'] = now
        if p['done'] == p['total']:
            print()

class CountryScraper:
    def __init__(self, country, playwright, proxy_pool):
        self.country = country
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
        proxy = self.get_next_proxy()
        proxy_settings = {
            'server': f"http://{proxy['server']}",
            'username': proxy['username'],
            'password': proxy['password']
        }
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            proxy=proxy_settings,
            args=[
                "--disable-quic",
                "--disable-http-cache",
                "--dns-prefetch-disable",
                "--disable-features=NetworkService,OutOfBlinkCors"
            ]
        )
        self.context = await self.browser.new_context(
            user_agent=random.choice(USER_AGENTS)
        )
        self.page = await self.context.new_page()

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except:
            pass
        try:
            if self.context:
                await self.context.close()
        except:
            pass
        try:
            if self.browser:
                await self.browser.close()
        except:
            pass
        self.page = self.context = self.browser = None

    async def ensure_browser(self):
        if not self.browser:
            await self.recreate_browser()

    async def process_product(self, gender, pid, date_subfolder, failed_log):
        if check_file(gender, pid, date_subfolder):
            progress[self.country]['done'] += 1
            await update_progress(self.country)
            return True

        for attempt in range(3):
            try:
                await self.ensure_browser()
                url = f'https://www2.hm.com/{COUNTRY_CONFIG[self.country]["domain"]}/productpage.{pid}.html'
                await self.page.goto(url, timeout=100000)
                html_content = await self.page.content()
                soup = BeautifulSoup(html_content, "html.parser")
                script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
                if script_tag:
                    json_data = json.loads(script_tag.string)
                    product_data = json_data['props']['pageProps']['productPageProps']['aemData']['productArticleDetails']
                    await save_json(gender, pid, product_data, date_subfolder)
                    progress[self.country]['done'] += 1
                    await update_progress(self.country)
                    return True
                else:
                    failed_log.error(f"{self.country} - Script tag not found for {pid}")
            except Exception as e:
                failed_log.error(f"{self.country} - Error processing {pid}: {e}")
            await self.recreate_browser()

        failed_log.error(f"{self.country} - Failed all attempts for {pid}")
        progress[self.country]['done'] += 1
        await update_progress(self.country)
        return False

async def process_country(country, playwright):
    start_time = datetime.now()
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)
    log_dir = Path(f"{country}/Logs/{today_str}")
    log_dir.mkdir(parents=True, exist_ok=True)
    failed_log = get_logger(f"{log_dir}/failed_urls.log")
    summary_log = get_logger(f"{log_dir}/summary.log")

    file_path = Path(f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json')
    with open(file_path) as json_file:
        urls_dict = json.load(json_file)

    total_products = sum(len(pids) for gender, pids in urls_dict.items()
                        if gender in COUNTRY_CONFIG[country]['genders'])
    progress[country]['total'] = total_products
    progress[country]['done'] = 0
    progress[country]['start_time'] = None
    progress[country]['last_update'] = 0

    print(f"\nStarting {country} with {total_products} products...")

    proxy_pool = COUNTRY_CONFIG[country]['proxies'].copy()
    random.shuffle(proxy_pool)

    task_queue = asyncio.Queue()
    for gender in COUNTRY_CONFIG[country]['genders']:
        if gender in urls_dict:
            for pid in urls_dict[gender]:
                if not check_file(gender, pid, date_subfolder):
                    task_queue.put_nowait((gender, pid))

    if task_queue.empty():
        print(f"{country} - All products already processed")
        return

    async def worker(worker_id):
        scraper = CountryScraper(country, playwright, proxy_pool)
        while not task_queue.empty():
            try:
                gender, pid = await task_queue.get()
                await scraper.process_product(gender, pid, date_subfolder, failed_log)
                task_queue.task_done()
            except Exception as e:
                logging.error(f"{country} - Worker {worker_id} error: {e}")
        await scraper.close()

    workers = [asyncio.create_task(worker(i)) for i in range(4)]
    await asyncio.gather(*workers)

    end_time = datetime.now()
    elapsed = end_time - start_time
    hours, remainder = divmod(elapsed.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    summary_log.info(f"{country} - Finished in {int(hours)}h {int(minutes)}m {int(seconds)}s")

async def main():
    print("Starting product data scraping...\n")
    async with async_playwright() as playwright:
        india_task = asyncio.create_task(process_country('India', playwright))
        uk_task = asyncio.create_task(process_country('UK', playwright))
        await asyncio.gather(india_task, uk_task)
    print("\nAll countries completed!")
    for country in ['India', 'UK']:
        p = progress[country]
        if p['total'] > 0:
            print(f"{country}: Completed {p['done']}/{p['total']} products")

if __name__ == "__main__":
    asyncio.run(main())