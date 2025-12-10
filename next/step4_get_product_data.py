import json
import asyncio
import logging
import argparse
from tqdm import tqdm
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date, datetime
from tqdm.asyncio import tqdm_asyncio
from playwright.async_api import async_playwright

# Logging setup
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
logger = logging.getLogger(__name__)

# Country configuration
COUNTRY_BROWSER_COUNT = {
    "India": 4,
    "UK": 4,
    "Saudi": 4,
    "UAE": 4
}

DAY_COUNTRY_MAP = {
    'Monday': ['India', 'UK'],
    'Wednesday': ['India', 'UK'],
    'Friday': ['India', 'UK'],
    'Tuesday': ['Saudi', 'UAE'],
    'Thursday': ['Saudi', 'UAE'],
    'Saturday': ['Saudi', 'UAE']
}

def get_today_countries():
    today = date.today().strftime('%A')
    # today = '2025-12-08'
    return DAY_COUNTRY_MAP.get(today, [])

def check_file(gender, name, date_subfolder):
    return (date_subfolder / 'Json_data' / gender / f'{name}.json').exists()

def save_json(gender, name, json_data, date_subfolder):
    try:
        path = date_subfolder / 'Json_data' / gender
        path.mkdir(parents=True, exist_ok=True)
        with open(path / f'{name}.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        tqdm.write(f"Error saving JSON file for {name}: {e}")

async def process_url(page, url, gender, date_subfolder):
    name = url.split('/')[-1].split('#')[0]
    if check_file(gender, name, date_subfolder):
        return False
    try:
        await page.goto(url, timeout=20000)
        await page.wait_for_timeout(2000)
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        data_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if data_tag and data_tag.string:
            data = json.loads(data_tag.string)
            queries = data['props']['pageProps']['dehydratedState']['queries']
            for query in queries:
                if isinstance(query['state']['data'], dict) and 'styleNumber' in query['state']['data']:
                    save_json(gender, name, query['state']['data'], date_subfolder)
                    return True
    except Exception as e:
        tqdm.write(f"Error processing URL {url}: {e}")
    return False

# ✅ FIXED: async def (was mistakenly written as sync def)
async def browser_worker(country, url_queue, date_subfolder, shared_pbar, worker_id):
    """
    Worker that processes URLs with automatic browser recycling to prevent memory leaks.
    """
    PAGES_PER_BROWSER = 300

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()
    urls_processed_since_recycle = 0

    while not url_queue.empty():
        if urls_processed_since_recycle >= PAGES_PER_BROWSER:
            tqdm.write(f"[{country}] Worker-{worker_id}: Recycling browser instance to clear memory...")

            try:
                if page and not page.is_closed():
                    await page.close()
                if browser and browser.is_connected():
                    await browser.close()
            except Exception as e:
                tqdm.write(f"[{country}] Worker-{worker_id} error during browser cleanup: {e}")

            await asyncio.sleep(1)  # Optional: small delay

            browser = await playwright.chromium.launch(headless=False)
            page = await browser.new_page()
            urls_processed_since_recycle = 0

        try:
            gender, url = url_queue.get_nowait()
            shared_pbar.set_description(f"{country} | {gender}")

            success = await process_url(page, url, gender, date_subfolder)
            if success:
                shared_pbar.update(1)

            urls_processed_since_recycle += 1

        except asyncio.QueueEmpty:
            break
        except Exception as e:
            tqdm.write(f"[{country}] Worker-{worker_id} error processing queue item: {e}")
            urls_processed_since_recycle += 1
        finally:
            url_queue.task_done()

    try:
        if page and not page.is_closed():
            await page.close()
        if browser and browser.is_connected():
            await browser.close()
    except Exception as e:
        tqdm.write(f"[{country}] Worker-{worker_id} error during final cleanup: {e}")
    
    await playwright.stop()


async def run_country(country, num_browsers):
    tqdm.write(f"[{country}] Starting with {num_browsers} browser(s)...")
    start_time = datetime.now()
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-02'
    base_dir = Path(f"{country}/Data/{today_str}")
    base_dir.mkdir(parents=True, exist_ok=True)

    url_file = base_dir / 'Item_urls' / f'{country}_unique_product_urls.json'
    if not url_file.exists():
        tqdm.write(f"[{country}] URL file missing: {url_file}")
        return

    with open(url_file, 'r', encoding='utf-8') as f:
        urls_dict = json.load(f)

    url_queue = asyncio.Queue()
    already_scraped = 0
    to_scrape = 0

    for gender, urls in urls_dict.items():
        for url in urls:
            name = url.split('/')[-1].split('#')[0]
            if check_file(gender, name, base_dir):
                already_scraped += 1
            else:
                await url_queue.put((gender, url))
                to_scrape += 1

    total_urls = already_scraped + to_scrape

    if to_scrape == 0:
        tqdm.write(f"[{country}] All URLs already scraped.")
        return

    tqdm.write(f"[{country}] Total URLs: {total_urls} | Already scraped: {already_scraped} | To scrape: {to_scrape}")
    shared_pbar = tqdm_asyncio(total=total_urls, desc=f"{country} | Starting", unit="url", leave=True)
    shared_pbar.update(already_scraped)

    await asyncio.gather(*[
        browser_worker(country, url_queue, base_dir, shared_pbar, i)
        for i in range(num_browsers)
    ])

    shared_pbar.close()

    elapsed = datetime.now() - start_time
    tqdm.write(f"[{country}] Finished in {str(elapsed).split('.')[0]}.")


async def main(countries, default_browser_count):
    tasks = []
    for country in countries:
        num_browsers = COUNTRY_BROWSER_COUNT.get(country, default_browser_count)
        tasks.append(run_country(country, num_browsers))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--countries', type=str, help='Comma-separated list of countries to run')
    parser.add_argument('--browsers-per-country', type=int, default=2, help='Default browser count per country')
    args = parser.parse_args()

    countries = args.countries.split(',') if args.countries else get_today_countries()
    if not countries:
        print("No countries to run today.")
    else:
        asyncio.run(main(countries, args.browsers_per_country))
