import json
import asyncio
import logging
from pathlib import Path
from tqdm.asyncio import tqdm
from datetime import date, datetime
from playwright.async_api import async_playwright

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Define country and store ID mapping by day
if day in ['Monday', 'Wednesday', 'Friday']:
    countries = {
        "Australia": '24009414/20309455',
        "Saudi": '25009530/20309454',
        "Spain": '24009400/20309449',
        "Turkey": "25009521/20309457"
    }
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    countries = {
        "UAE": '25009531/20309454',
        "UK": '24009406/20309455',
        "USA": '24009477/20309455'
    }
else:
    countries = {}

# Function to fetch product IDs using Playwright
async def get_json(page, country, storeId, cid):
    try:
        url = f'https://www.pullandbear.com/itxrest/3/catalog/store/{storeId}/category/{cid}/product?languageId=-1&showProducts=false&appId=1'
        if country == 'USA':
            url = f'https://www.pullandbear.com/itxrest/3/catalog/store/{storeId}/category/{cid}/product?languageId=-15&showProducts=false&appId=1'

        await page.goto(url)
        content = await page.text_content("pre")
        json_data = json.loads(content)
        return json_data.get('productIds', [])
    except Exception as e:
        logging.error(f"Error processing {country} category {cid}: {e}")
        return []

# Main async function using Playwright
async def main():
    bar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        for country, store_id in countries.items():
            logging.info(f"Processing country: {country}...")
            p_dict = {}

            file_path = Path(f'{country}/Data/{today_str}/Item_urls/{country}_category_links.json')
            if not file_path.exists():
                logging.error(f"Missing file: {file_path}")
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    subids = json.load(f)
            except Exception as e:
                logging.error(f"Failed to read JSON for {country}: {e}")
                continue

            for gender in tqdm(subids, desc=f"{country} - Genders", bar_format=bar_format, ascii=(' ', '*')):
                p_dict[gender] = {}
                for category, c_dict in tqdm(subids[gender].items(), desc=gender, leave=False, bar_format=bar_format, ascii=(' ', '*')):
                    cid = c_dict.get('id') or c_dict.get('cid')
                    if not cid:
                        logging.warning(f"Missing category id in {country} -> {gender} -> {category}")
                        continue
                    product_ids = await get_json(page, country, store_id, cid)
                    p_dict[gender][category] = product_ids

            if p_dict:
                try:
                    output_path = Path(f'{country}/Data/{today_str}/Item_urls')
                    output_path.mkdir(parents=True, exist_ok=True)
                    output_file = output_path / f'{country}_product_ids.json'
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(p_dict, f, ensure_ascii=False, indent=4)
                    logging.info(f"Saved product IDs for {country} to {output_file}")
                except Exception as e:
                    logging.error(f"Failed to save product IDs for {country}: {e}")
            else:
                logging.info(f"No data to save for {country}.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
