import json
import asyncio
import logging
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date
from proxy_code import async_get_page_source  # Import the new async function

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def process_url(country, gender, category, url, file_path: Path, scraped_data: dict):
    for attempt in range(3):
        try:
            html = await async_get_page_source(url)
            soup = BeautifulSoup(html, "html.parser")
            script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if not script_tag:
                continue

            json_data = json.loads(script_tag.string)
            curl = url
            pages = json_data.get('props', {}).get('pageProps', {}).get('plpProps', {}).get('productListingSectionProps', {}).get('productListingData', {}).get('pagination', {}).get('totalPages', 0)
 

            pcodes = []
            if gender not in scraped_data:
                scraped_data[gender] = {}
            if category not in scraped_data[gender]:
                scraped_data[gender][category] = []

            for page_num in range(1, pages + 1):
                turl = f"{curl}?page={page_num}"
                html = await async_get_page_source(turl)
                soup = BeautifulSoup(html, "html.parser")
                product_grid = soup.find("ul", {"data-elid": "product-grid"})

                if product_grid:
                    product_cards = product_grid.find_all("article")
                    page_pcodes = [card.get('data-articlecode') for card in product_cards if card.get('data-articlecode')]
                    pcodes.extend(page_pcodes)

                    # Save immediately after each page
                    scraped_data[gender][category] = pcodes
                    with file_path.open("w", encoding='utf-8') as f:
                        json.dump(scraped_data, f, ensure_ascii=False, indent=4)
                    logging.info(f"Saved after page {page_num}: {len(pcodes)} total products for {gender} > {category}")

            logging.info(f"{url} - {len(pcodes)} products scraped")
            return pcodes

        except Exception as e:
            logging.error(f"{country} - Error on URL: {url} - {e}")

    logging.error(f"{country} - All attempts failed for URL: {url}")
    return None

async def scrape_country(country: str):
    today_str = date.today().strftime('%Y-%m-%d')
    output_dir = Path(f"{country}/Data/{today_str}/Item_urls")
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = output_dir / f"{country}_category_urls.json"
    file_path = output_dir / f"{country}_product_urls.json"

    with input_path.open() as f:
        url_dict = json.load(f)

    if file_path.exists():
        with file_path.open() as f:
            scraped_data = json.load(f)
    else:
        scraped_data = {}

    task_queue: asyncio.Queue = asyncio.Queue()
    for gender, categories in url_dict.items():
        for category, url in categories.items():
            if gender not in scraped_data:
                scraped_data[gender] = {}
            # Enqueue only if not scraped yet or empty
            if category not in scraped_data[gender] or not scraped_data[gender][category]:
                task_queue.put_nowait((gender, category, url))

    if task_queue.empty():
        logging.info(f"{country} - All categories already scraped.")
        return

    async def worker(worker_id: int):
        try:
            while True:
                try:
                    gender, category, url = await asyncio.wait_for(task_queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    if task_queue.empty():
                        break
                    continue
                try:
                    await process_url(country, gender, category, url, file_path, scraped_data)
                except Exception as e:
                    logging.error(f"{country} - Worker {worker_id} error: {e}")
                finally:
                    task_queue.task_done()
        finally:
            # No per-worker resources to close
            pass

    workers = [asyncio.create_task(worker(i)) for i in range(2)]
    await task_queue.join()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

async def main():
    countries = ['India']
    await asyncio.gather(*(scrape_country(country) for country in countries))

if __name__ == "__main__":
    asyncio.run(main())