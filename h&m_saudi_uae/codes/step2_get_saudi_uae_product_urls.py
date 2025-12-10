import os
import json
import random
import asyncio
import logging
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date, datetime
from urllib.parse import urljoin
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/general_scraper.log', mode='a'),
    ]
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

def get_logger(log_path):
    log_path = str(log_path)
    logger = logging.getLogger(log_path)
    logger.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == os.path.abspath(log_path) for h in logger.handlers):
        fh = logging.FileHandler(log_path, mode='a')
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

class PersistentScraper:
    def __init__(self, country, playwright, proxy_pool=None):
        self.country = country
        self.playwright = playwright
        self.proxy_pool = proxy_pool or []
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
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-quic",
                "--disable-http-cache",
                "--dns-prefetch-disable",
                "--disable-features=NetworkService,OutOfBlinkCors"
            ]
        )
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

    async def process_url(self, gender, category, url, log_dir, file_path, scraped_data):
        failed_log = get_logger(log_dir / "failed_urls.log")
        category_log = get_logger(log_dir / f"{gender}_{category}_log.txt")

        for attempt in range(3):
            try:
                await self.ensure_browser()
                await self.page.goto(url, wait_until='domcontentloaded', timeout=10000)
                await asyncio.sleep(random.uniform(2, 4))

                # Check for "no products" message before scraping
                html = await self.page.content()
                soup = BeautifulSoup(html, "html.parser")
                not_found_tag = soup.find("p", string=lambda s: s and "we couldn't find the products you're looking for" in s.lower())
                if not_found_tag:
                    logging.info(f"{self.country} - No products found at URL: {url}")
                    return None  # Skip to next URL

                if gender not in scraped_data:
                    scraped_data[gender] = {}
                if category not in scraped_data[gender]:
                    scraped_data[gender][category] = {}

                purls = {}
                page_num = 1
                while True:
                    paginated_url = f"{url}?page={page_num}"
                    await self.page.set_viewport_size({"width": 1920, "height": 1080})
                    await self.page.goto(paginated_url, wait_until='domcontentloaded', timeout=6000)
                    await asyncio.sleep(random.uniform(2, 4))

                    html = await self.page.content()
                    soup = BeautifulSoup(html, "html.parser")

                    # Repeat the check just in case pagination shows the message too
                    not_found_tag = soup.find("p", string=lambda s: s and "we couldn't find the products you're looking for" in s.lower())
                    if not_found_tag:
                        logging.info(f"{self.country} - No products found at page {page_num}: {paginated_url}")
                        break

                    product_cards = soup.find_all("div", class_="product-item")
                    if not product_cards:
                        logging.info(f"{self.country} - Pagination end at page {page_num} - {url}")
                        break

                    for card in product_cards:
                        a_tag = card.find("a")
                        main_sku = card.get('data-id')
                        if a_tag and main_sku:
                            href = a_tag.get('href')
                            if href:
                                full_link = urljoin(url, href)
                                purls[main_sku] = full_link

                    scraped_data[gender][category].update(purls)

                    with file_path.open("w", encoding='utf-8') as f:
                        json.dump(scraped_data, f, ensure_ascii=False, indent=4)

                    category_log.info(f"Page {page_num} done for {gender}/{category} - {len(scraped_data[gender][category])} total")
                    page_num += 1

                return purls

            except Exception as e: 
                failed_log.error(f"{self.country} - Error on URL: {url} - {e}", exc_info=True)
                await self.recreate_browser()

        failed_log.error(f"{self.country} - All attempts failed for URL: {url}")
        return None

async def scrape_country(country, playwright):
    start_time = datetime.now()
    today_str = date.today().strftime('%Y-%m-%d')

    input_path = Path(f"{country}/{country}_category_urls.json")
    output_dir = Path(f"{country}/Data/{today_str}/Item_urls")
    log_dir = Path(f"{country}/Logs/{today_str}")

    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    file_path = output_dir / f"{country}_product_urls.json"

    with input_path.open() as f:
        url_dict = json.load(f)

    scraped_data = {}
    if file_path.exists():
        with file_path.open() as f:
            scraped_data = json.load(f)

    task_queue = asyncio.Queue()
    for gender, categories in url_dict.items():
        for category, url in categories.items():
            if category not in scraped_data.get(gender, {}):
                await task_queue.put((gender, category, url))

    if task_queue.empty():
        logging.info(f"{country} - All categories already scraped.")
        return

    proxy_pool = []

    async def worker(worker_id):
        scraper = PersistentScraper(country, playwright, proxy_pool)
        while not task_queue.empty():
            try:
                gender, category, url = await task_queue.get()
                await scraper.process_url(gender, category, url, log_dir, file_path, scraped_data)
                task_queue.task_done()
            except Exception as e:
                logging.error(f"{country} - Worker {worker_id} error: {e}", exc_info=True)
        await scraper.close()

    workers = [asyncio.create_task(worker(i)) for i in range(2)]
    await asyncio.gather(*workers)

    elapsed = datetime.now() - start_time
    get_logger(log_dir / "summary.log").info(f"{country} - Finished in {elapsed}")
    print(f"{country} - Finished in {elapsed}")

async def main():
    countries = ['Saudi', 'UAE']
    async with async_playwright() as playwright:
        await asyncio.gather(*(scrape_country(country, playwright) for country in countries))

if __name__ == "__main__":
    asyncio.run(main())
