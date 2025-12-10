import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import date, datetime
from bs4 import BeautifulSoup
from proxy_code import async_get_page_source 


# Setup logging (simple, no file handlers)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def check_file(gender, pid, date_subfolder):
    return os.path.exists(f'{date_subfolder}/Json_data/{gender}/{pid}.json')

async def save_json(gender, pid, json_data, date_subfolder):
    try:
        json_file_path = date_subfolder / 'Json_data' / gender
        json_file_path.mkdir(parents=True, exist_ok=True)
        with open(json_file_path / f'{pid}.json', 'w') as outfile:
            json.dump(json_data, outfile, indent=4)
        logging.info(f"Saved JSON for {pid}")
    except Exception as e:
        logging.error(f"Error saving JSON for {pid}: {e}")

COUNTRY_CONFIG = {
        'UK': 'en_gb'
    }

async def process_product(country, gender, pid, date_subfolder):
    if check_file(gender, pid, date_subfolder):
        return True

    try:
        url = f'https://www2.hm.com/{COUNTRY_CONFIG[country]}/productpage.{pid}.html'
        html_content = await async_get_page_source(url, ['script#__NEXT_DATA__'])
        soup = BeautifulSoup(html_content, "html.parser")
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if script_tag:
            logging.info(f"{country} - Processing {pid}")
            json_data = json.loads(script_tag.string)
            product_data = json_data['props']['pageProps']['productPageProps']['aemData']['productArticleDetails']
            await save_json(gender, pid, product_data, date_subfolder)
            return True
        else:
            logging.error(f"{country} - Script tag not found for {pid}")
    except Exception as e:
        logging.error(f"{country} - Error processing {pid}: {e}")

async def process_country(country):
    start_time = datetime.now()
    
    today_str =date.today().strftime('%Y-%m-%d')
    # today_str = '2025-10-02'
    
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    file_path = Path(f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json')
    with open(file_path) as json_file:
        urls_dict = json.load(json_file)

    task_queue = asyncio.Queue()
    for gender, pids in urls_dict.items():
        for pid in pids:
            if not check_file(gender, pid, date_subfolder):
                task_queue.put_nowait((gender, pid))

    if task_queue.empty():
        print(f"{country} - All products already processed")
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

    workers = [asyncio.create_task(worker(i)) for i in range(4)]
    await asyncio.gather(*workers)

    end_time = datetime.now()
    elapsed = end_time - start_time
    hours, remainder = divmod(elapsed.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    logging.info(f"{country} - Finished in {int(hours)}h {int(minutes)}m {int(seconds)}s")
    print(f"{country} - Finished in {int(hours)}h {int(minutes)}m {int(seconds)}s")

async def main():
    
    await process_country('UK')

if __name__ == "__main__":
    asyncio.run(main())