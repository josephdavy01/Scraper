import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import date, datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_json(date_subfolder, gender, category, fname, data):
    try:
        json_file_path = Path(date_subfolder) / 'Json_data' / gender / category
        json_file_path.mkdir(parents=True, exist_ok=True)
        with open(json_file_path / f'{fname}.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file: {e}")

def check_file(gender, category, name, date_subfolder):
    file_path = Path(date_subfolder) / 'Json_data' / gender / category / f'{name}.json'
    return file_path.exists()

async def fetch_url(p, url, date_subfolder, gender, category, sem):
    fname = url.rstrip('/').split('/')[-1].replace('?variant=', '_')
    if check_file(gender, category, fname, date_subfolder):
        return

    async with sem:
        try:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(url, timeout=60000)
            page_source = await page.content()
            soup = BeautifulSoup(page_source, 'html.parser')

            product_json_data = {}
            variant_json_data = {}
            images = []

            product_script_tags = soup.find_all('script', type='application/ld+json')
            if product_script_tags:
                json_content = product_script_tags[-1].string
                if json_content:
                    product_json_data = json.loads(json_content)

            variant_script_tags = soup.find_all('script', type='application/json')
            for script_tag in variant_script_tags:
                if script_tag.string and script_tag.string.strip().startswith('{"variants":'):
                    json_content = script_tag.string
                    variant_json_data = json.loads(json_content)

            image_divs = soup.find_all('div', class_='slider__item')
            for image_tag in image_divs:
                image_id = image_tag.get('data-media-id', None)
                image_color = image_tag.get('thumbnail-color', None)
                img_element = image_tag.find('img')
                image_url = img_element.get('src') if img_element else None
                images.append({'id': image_id, 'color': image_color, 'url': image_url})

            data = {
                'product': product_json_data,
                'variants': variant_json_data.get('variants', []),
                'images': images
            }

            save_json(date_subfolder, gender, category, fname, data)
            await browser.close()

        except Exception as e:
            logging.error(f"Error processing URL {url}: {e}")

async def main():
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-08'
    country = 'UAE'

    logging.info(f'Now starting {country} products...')
    date_subfolder = f'{country}/Data/{today_str}'

    file_path = Path(f'{date_subfolder}/Item_urls/{country}_unique_product_urls.json')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            urls_dict = json.load(f)
    except Exception as e:
        logging.critical(f"Could not load URL JSON file: {e}")
        return

    sem = asyncio.Semaphore(6) 

    async with async_playwright() as p:
        try:
            for gender, categories in urls_dict.items():
                for category, url_list in categories.items():
                    logging.info(f'Now starting {gender} {category} products...')
                    logging.info(f'Number of URLs: {len(url_list)}')

                    tasks = [
                        fetch_url(p, url, date_subfolder, gender, category, sem)
                        for url in url_list
                    ]
                    await asyncio.gather(*tasks)
                    logging.info(f'{gender} {category} section completed.')

            logging.info(f'{country} products completed.')

        except Exception as e:
            logging.critical(f"Unexpected error in main execution: {e}")

if __name__ == "__main__":
    asyncio.run(main())