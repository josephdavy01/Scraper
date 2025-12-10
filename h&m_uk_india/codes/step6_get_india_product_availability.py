import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import date, datetime
from bs4 import BeautifulSoup
from proxy_code import async_get_page_source_without_proxy

today_str = date.today().strftime('%Y-%m-%d')

day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Setup logging (simple, no file handlers)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def check_file(gender, name, date_subfolder):
    file_path = f'{date_subfolder}/Availability/{gender}/{name}.json'
    return os.path.exists(file_path)

async def save_json(gender, name, json_data, date_subfolder):
    try:
        json_file_path = date_subfolder / 'Availability' / gender
        json_file_path.mkdir(parents=True, exist_ok=True)
        with open(json_file_path / f'{name}.json', 'w') as outfile:
            json.dump(json_data, outfile, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")

COUNTRY_ENDPOINTS = {
    'India': 'in'
}

async def process_product(country, gender, pid, date_subfolder):
    for attempt in range(3):
        try:
            country_code = COUNTRY_ENDPOINTS[country]
            url = f'https://www2.hm.com/hmwebservices/service/product/{country_code}/availability/{pid[:-3]}.json'
            html_content = await async_get_page_source_without_proxy(url)
            soup = BeautifulSoup(html_content, "html.parser")
            pre_tag = soup.find('pre')
            if pre_tag and pre_tag.string:
                json_data = json.loads(pre_tag.string)
                await save_json(gender, pid[:-3], json_data, date_subfolder)
                return True
            else:
                logging.error(f"{country} - No JSON data found for PID {pid}")
        except Exception as e:
            logging.error(f"{country} - Error processing product {pid}: {e}")
    logging.error(f"{country} - All attempts failed for product {pid}")
    return False

async def process_country(country):
    start_time = datetime.now()
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    #today_str='2025-09-22'
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    file_path = Path(f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json')
    with open(file_path) as json_file:
        urls_dict = json.load(json_file)

    task_queue = asyncio.Queue()
    for gender, pids in urls_dict.items():
        for pid in pids:
            if not check_file(gender, pid[:-3], date_subfolder):
                task_queue.put_nowait((gender, pid))

    if task_queue.empty():
        logging.info(f"{country} - All products already processed.")
        return

    async def worker(worker_id):
        while not task_queue.empty():
            try:
                gender, pid = await task_queue.get()
                success = await process_product(country, gender, pid, date_subfolder)
                if success:
                    logging.info(f"{country} - Processed {gender}/{pid}")
                task_queue.task_done()
            except Exception as e:
                logging.error(f"{country} - Worker {worker_id} error: {e}")

    workers = [asyncio.create_task(worker(i)) for i in range(15)]
    await asyncio.gather(*workers)

    end_time = datetime.now()
    elapsed = end_time - start_time
    hours, remainder = divmod(elapsed.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    logging.info(f"{country} - Finished in {int(hours)}h {int(minutes)}m {int(seconds)}s")
    print(f"{country} - Finished in {int(hours)}h {int(minutes)}m {int(seconds)}s")

async def main():
    await process_country('India')

if __name__ == "__main__":
    asyncio.run(main())