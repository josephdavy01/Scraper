import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import date, datetime
from playwright.async_api import async_playwright

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def save_json(pid, json_data, save_path):
    """Save JSON data to a file."""
    try:
        os.makedirs(save_path, exist_ok=True)
        with open(os.path.join(save_path, f'{pid}.json'), 'w', encoding='utf-8') as outfile:
            json.dump(json_data, outfile, ensure_ascii=False, indent=4)
        logging.info(f'Saved JSON data for product ID {pid} to {save_path}')
    except Exception as e:
        logging.error(f'Error saving JSON for product ID {pid}: {e}')

async def get_composition(pids_list, code, save_path, page):
    """Fetch composition data for a list of product IDs."""
    for pid in pids_list:
        if os.path.exists(os.path.join(save_path, f'{pid}.json')):
            logging.info(f'Product ID {pid} already exists, skipping.')
            continue
        url = f'https://www.zara.com/{code}/en/product/{pid}/extra-detail?ajax=true'
        try:
            await page.goto(url)
            await page.wait_for_selector("pre")
            response_body = await page.locator("pre").inner_text()
            json_data = json.loads(response_body)
            await save_json(pid, json_data, save_path)

        except Exception as e:
            logging.error(f"Error processing URL {url}: {e}")

def get_new_pids(new_list, old_list):
    old_list = [entry.replace('.json', '') for entry in old_list]
    return list(set(map(str, new_list)) - set(map(str, old_list)))

async def main():
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    # Filter countries based on the day of the week
    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = {
            'Australia': 'au',
            'Canada': 'ca',
            'India': 'in',
            'Saudi': 'sa',
            'Spain': 'es'
        }
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = {
            'Turkey': 'tr',
            'UAE': 'ae',
            'UK': 'uk',
            'USA': 'us'
        }
    else:
        countries = {}

    # Initialize Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            for country, code in countries.items():
                if not code:
                    logging.error(f'No country code found for {country}')
                    continue

                root_path = os.path.join(country, 'Data', today_str, 'Item_urls')
                save_path = Path(country) / 'Extra_details_data'
                save_path.mkdir(parents=True, exist_ok=True)

                if not os.path.exists(root_path):
                    logging.warning(f'Root path {root_path} does not exist, skipping {country}')
                    continue

                for file in os.listdir(root_path):
                    if not file.endswith('product_ids.json'):
                        continue

                    logging.info(f'Processing {country} - {today_str} - {file}')
                    try:
                        with open(os.path.join(root_path, file), 'r', encoding='utf-8') as json_file:
                            pids_dict = json.load(json_file)
                    except Exception as e:
                        logging.error(f'Error reading {file} in {root_path}: {e}')
                        continue

                    if not isinstance(pids_dict, list):
                        logging.error(f'Invalid format in {file}: Expected a list, got {type(pids_dict)}')
                        continue

                    existing_files = os.listdir(save_path) if os.path.exists(save_path) else []
                    pids_list = get_new_pids(pids_dict, existing_files)

                    logging.info(f'Fetching {len(pids_list)} new records for {country} on {today_str}')
                    await get_composition(pids_list, code, save_path, page)
        except Exception as e:
            logging.error(f'Unexpected error in main loop: {e}')
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())