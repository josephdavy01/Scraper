import os
import json
import asyncio
import logging
from datetime import date
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from proxy_code import async_get_page_scroll_load

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

POP_KEYS = [ 'sports', 'sportstyle']
COUNTRIES = {
    "USA": "https://www.asics.com/us/en-us"
    # "UK": "https://www.asics.com/gb/en-gb"
}
SEMAPHORE_LIMIT = 1
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

async def get_product_urls(url, base_url):
    all_product_urls = set()
    page_count = 0
    current_url = url

    try:
        page_count += 1
        logging.info(f"Processing page {page_count}: {current_url}")
        html = await async_get_page_scroll_load(current_url, elements_to_wait=None)
        if not html:
            logging.error(f"Failed to get page content for {current_url}")
            return []
        soup = BeautifulSoup(html, 'html.parser')
        product_links = soup.select("a.product-tile__link")
        for link in product_links:
            href = link.get("href")
            if href:
                full_url = urljoin(base_url, href)
                all_product_urls.add(full_url)
        logging.info(f"Page {page_count}: Found {len(product_links)} URLs")
        logging.info(f'Total unique product URLs from {url}: {len(all_product_urls)}')
        return list(all_product_urls)
    except Exception as e:
        logging.error(f'A critical error occurred in get_product_urls for {url}: {e}')
        return list(all_product_urls) if all_product_urls else []

async def fetch_product_urls(gender: str, category: str, url: str, country: str):
    async with semaphore:
        logging.info(f'[{gender} - {category}] Processing: {url}')
        try:
            base_url = COUNTRIES[country]
            result = await get_product_urls(url, base_url)
            logging.info(f'[{gender} - {category}] URLs found: {len(result)}')
            return gender, category, result
        except Exception as e:
            logging.error(f'Error processing {gender} - {category}: {e}')
            return gender, category, []

async def worker(worker_id, task_queue, purl_list):
    while not task_queue.empty():
        try:
            gender, category, url, country = await task_queue.get()
            gender, category, result = await fetch_product_urls(gender, category, url, country)
            if gender not in purl_list:
                purl_list[gender] = {}
            purl_list[gender][category] = result
            logging.info(f'Collected {len(result)} URLs for {gender} - {category}')
        except Exception as e:
            logging.error(f"Worker {worker_id} error: {e}")
        finally:
            task_queue.task_done()

async def process_country(country: str, today_str: str):
    read_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_category_urls.json'
    if not os.path.exists(read_file_path):
        logging.error(f"Category URL file not found: {read_file_path}")
        return

    with open(read_file_path, encoding='utf-8') as f:
        url_dict = json.load(f)

    output_dir = f'{country}/Data/{today_str}/Item_urls'
    os.makedirs(output_dir, exist_ok=True)
    file_path = f'{output_dir}/{country}_product_urls.json'

    purl_list = {}
    task_queue = asyncio.Queue()

    try:
        for category, url in url_dict.items():
            if category in POP_KEYS or "shop_all" in category or url.startswith("javascript"):
                logging.info(f'Skipping excluded category: [{category}]')
                continue
            task_queue.put_nowait((category, category, url, country))  # gender = category

        workers = [asyncio.create_task(worker(i, task_queue, purl_list)) for i in range(2)]
        await asyncio.gather(*workers)

    except Exception as e:
        logging.error(f"Error processing {country}: {e}")

    with open(file_path, "w", encoding='utf-8') as f:
        json.dump(purl_list, f, ensure_ascii=False, indent=2)

    total_urls = sum(len(links) for cats in purl_list.values() for links in cats.values())
    print(f'\n--- {country} Scraping Complete ---')
    print(f'Product URLs saved to {file_path}')
    print(f'Total Unique URLs Extracted: {total_urls}')
    for gender, categories in purl_list.items():
        print(f'\nGender: {gender}')
        for category, urls in categories.items():
            print(f'  - {category}: {len(urls)} URLs')

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    await asyncio.gather(*(process_country(country, today_str) for country in COUNTRIES.keys()))

if __name__ == "__main__":
    asyncio.run(main())