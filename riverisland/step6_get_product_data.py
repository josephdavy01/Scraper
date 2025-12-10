import asyncio
import json
import logging
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from multiprocessing import Process

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def save_json(gender, category, filename, json_data, date_subfolder):
    try:
        json_file_path = date_subfolder / 'Json_data' / gender / category
        json_file_path.mkdir(parents=True, exist_ok=True)
        with open(json_file_path / f'{filename}.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for {filename}: {e}")


def check_file(gender, category, name, date_subfolder):
    file_path = date_subfolder / 'Json_data' / gender / category / f'{name}.json'
    return file_path.exists()


async def get_json(semaphore, browser, date_subfolder, gender, category, urls):
    async with semaphore:
        page = await browser.new_page()
        for url in urls:
            filename = url.rstrip('/').split('/')[-1]
            if check_file(gender, category, filename, date_subfolder):
                continue

            try:
                logging.info(f"Fetching: {url}")
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_load_state("networkidle")
                html_content = await page.content()

                soup = BeautifulSoup(html_content, "html.parser")
                script_tag = soup.find("script", {"id": "__NEXT_DATA__"})

                if script_tag:
                    json_data = json.loads(script_tag.string)
                    data = json_data['props']['pageProps']['apolloClientCache']

                    for key in data.keys():
                        if 'Product:' in key:
                            save_json(gender, category, filename, data[key], date_subfolder)
                            break

            except Exception as e:
                logging.error(f"Error processing the webpage for {url}: {e}")
        await page.close()


async def scrape_country(country):
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')

    logging.info(f'Starting {country} products...')
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    file_path = date_subfolder / 'Item_urls' / f'{country}_unique_product_urls.json'
    if not file_path.exists():
        logging.error(f"Missing URL file: {file_path}")
        return

    with open(file_path, 'r') as f:
        url_dict = json.load(f)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        semaphore = asyncio.Semaphore(2)
        tasks = []

        for gender, categories in url_dict.items():
            for category, urls in categories.items():
                logging.info(f'Queued task: {gender} {category} products...')
                tasks.append(get_json(semaphore, browser, date_subfolder, gender, category, urls))

        await asyncio.gather(*tasks)
        await browser.close()

    logging.info(f'{country} products completed.')


def run_country_process(country):
    asyncio.run(scrape_country(country))


def main():
    countries = ['UK', 'USA']
    processes = []

    for country in countries:
        p = Process(target=run_country_process, args=(country,))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()


if __name__ == "__main__":
    main()
