import json
import asyncio
import logging
from tqdm import tqdm
from pathlib import Path
from datetime import date, datetime
from playwright.async_api import async_playwright

bar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_json(gender, category, url, json_data, date_subfolder):
    try:
        product_name_id = url.split('/')[-1].replace('.html', '')
        json_file_path = date_subfolder / 'Json_data' / gender / category
        json_file_path.mkdir(parents=True, exist_ok=True)

        file_path = f'{json_file_path}/{product_name_id}.json'

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        logging.info(f"Saved to: {file_path}")
    except Exception as e:
        logging.error(f"Error saving JSON for {product_name_id}: {e}")


def check_file(gender, category, url, date_subfolder):
    output_dir = date_subfolder / 'Json_data' / gender / category
    output_dir.mkdir(parents=True, exist_ok=True)
    name = url.split('/')[-1].replace('.html', '')
    file_path = date_subfolder / 'Json_data' / gender / category / f"{name}.json"
    return file_path.exists()


async def process_urls(page, gender, category, url_list, date_subfolder):
    unique_product_ids = []

    for url in url_list:
        if not check_file(gender, category, url, date_subfolder):
            try:
                await page.goto(f'{url}?ajax=true')
                await page.wait_for_selector("pre")
                response_body = await page.locator("pre").inner_text()
                json_data = json.loads(response_body)

                save_json(gender, category, url, json_data, date_subfolder)

                temp = [j['productId'] for j in json_data['product']['detail']['colors']]
                unique_product_ids.extend(temp)

            except Exception as e:
                logging.error(f"Error processing URL {url}: {e}")

    return unique_product_ids


async def fetch_country_data(playwright, country, code, today_str):
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()

    try:
        logging.info(f"Starting {country}...")
        date_subfolder = Path(country) / 'Data' / today_str
        date_subfolder.mkdir(parents=True, exist_ok=True)

        file_path = Path(f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json')
        try:
            with open(file_path, "r", encoding='utf-8') as json_file:
                urls_dict = json.load(json_file)
        except FileNotFoundError:
            logging.error(f"Missing: {file_path}")
            return

        unique_product_ids = []

        for gender in tqdm(urls_dict, desc=f"{country} - Genders", bar_format=bar_format, ascii=(' ', '*')):
            for category, urls in tqdm(urls_dict[gender].items(), desc=gender, leave=False, bar_format=bar_format, ascii=(' ', '*')):
                tqdm.write(f"[INFO] {country}: {gender} {category}")
                ids = await process_urls(page, gender, category, urls, date_subfolder)
                unique_product_ids.extend(ids)
                tqdm.write(f"[DONE] {country}: {gender} {category}")

        output_dir = Path(f'{country}/Data/{today_str}/Item_urls')
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(f'{output_dir}/{country}_product_ids.json', "w", encoding='utf-8') as outfile:
            json.dump(unique_product_ids, outfile, ensure_ascii=False, indent=4)

        logging.info(f"{country} done.")
    except Exception as e:
        logging.error(f"Unhandled error in fetch_country_data for {country}: {e}")
    finally:
        await browser.close()


async def main():
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = {
            'Australia': 'au',
            'Canada': 'ca',
            'India': 'in',
            'Saudi': 'sa',
            'Spain': 'es'
        }
    else:
        countries = {
            'Turkey': 'tr',
            'UAE': 'ae',
            'UK': 'uk',
            'USA': 'us'
        }

    async with async_playwright() as playwright:
        try:
            tasks = [
                fetch_country_data(playwright, country, code, today_str)
                for country, code in countries.items()
            ]
            await asyncio.gather(*tasks)
        except Exception as e:
            logging.error(f"Fatal error during scraping: {e}")

if __name__ == "__main__":
    asyncio.run(main())