import os
import json
import logging
import asyncio
import random
from pathlib import Path
from datetime import date, datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

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

# Fixed: PROXY_POOL now correctly uses PROXIES
PROXY_POOL = {
    'India': [PROXIES['India']],
    'UK': [PROXIES['UK']]
}

COUNTRY_ENDPOINTS = {
    "India": "in",
    "UK": "gb"
}

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/availability_scraper.log', mode='a'),
    ]
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

def get_logger(log_path):
    logger = logging.getLogger(log_path)
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, mode='a')
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    fh.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(fh)
    return logger

async def save_json(gender, name, json_data, date_subfolder):
    try:
        json_file_path = date_subfolder / 'Availability' / gender
        json_file_path.mkdir(parents=True, exist_ok=True)
        with open(json_file_path / f'{name}.json', 'w') as outfile:
            json.dump(json_data, outfile, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")

def check_file(gender, name, date_subfolder):
    file_path = f'{date_subfolder}/Availability/{gender}/{name}.json'
    return os.path.exists(file_path)

class CountryWorker:
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
        for attempt in range(3):
            try:
                await self.ensure_browser()
                country_code = COUNTRY_ENDPOINTS[self.country]
                url = f'https://www2.hm.com/hmwebservices/service/product/{country_code}/availability/{pid[:-3]}.json'
                await self.page.goto(url, timeout=100000)
                html_content = await self.page.content()
                soup = BeautifulSoup(html_content, "html.parser")
                pre_tag = soup.find('pre')
                if pre_tag and pre_tag.string:
                    json_data = json.loads(pre_tag.string)
                    await save_json(gender, pid[:-3], json_data, date_subfolder)
                    return True
                else:
                    failed_log.error(f"{self.country} - No JSON data found for PID {pid}")
            except PlaywrightTimeoutError:
                failed_log.error(f"{self.country} - Timeout on product {pid}")
            except Exception as e:
                failed_log.error(f"{self.country} - Error processing product {pid}: {e}")
            await self.recreate_browser()  # rotate proxy and recreate browser each failure
        failed_log.error(f"{self.country} - All attempts failed for product {pid}")
        return False

async def process_country(country, playwright):
    start_time = datetime.now()
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    today_str = "2025-09-02"


    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    log_dir = Path(f"{country}/Logs/{today_str}")
    log_dir.mkdir(parents=True, exist_ok=True)

    failed_log = get_logger(f"{log_dir}/failed_urls.log")
    summary_log = get_logger(f"{log_dir}/summary.log")
    category_log = get_logger(f"{log_dir}/availability.log")

    file_path = Path(f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json')
    with open(file_path) as json_file:
        urls_dict = json.load(json_file)

    proxy_pool = PROXY_POOL[country].copy()
    random.shuffle(proxy_pool)

    task_queue = asyncio.Queue()
    for gender, pids in urls_dict.items():
        for pid in pids:
            if not check_file(gender, pid[:-3], date_subfolder):
                task_queue.put_nowait((gender, pid))

    if task_queue.empty():
        logging.info(f"{country} - All products already processed.")
        return

    async def worker(worker_id):
        worker = CountryWorker(country, playwright, proxy_pool)
        while not task_queue.empty():
            try:
                gender, pid = await task_queue.get()
                success = await worker.process_product(gender, pid, date_subfolder, failed_log)
                if success:
                    category_log.info(f"{country} - Processed {gender}/{pid}")
                task_queue.task_done()
            except Exception as e:
                logging.error(f"{country} - Worker {worker_id} error: {e}")
        await worker.close()

    workers = [asyncio.create_task(worker(i)) for i in range(2)]
    await asyncio.gather(*workers)

    end_time = datetime.now()
    elapsed = end_time - start_time
    hours, remainder = divmod(elapsed.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    summary_log.info(f"{country} - Finished in {int(hours)}h {int(minutes)}m {int(seconds)}s")
    print(f"{country} - Finished in {int(hours)}h {int(minutes)}m {int(seconds)}s")

async def main():
    async with async_playwright() as playwright:
        await asyncio.gather(
            process_country('India', playwright),
            process_country('UK', playwright)
        )

if __name__ == "__main__":
    asyncio.run(main())
