import asyncio
import json
import logging
from pathlib import Path
from datetime import date, datetime
from tqdm.asyncio import tqdm_asyncio
from playwright.async_api import async_playwright

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Country/storeId map by day
if day in ['Monday', 'Wednesday', 'Friday']:
    countries = {
        'Canada': '54009628/50331143',
        'Saudi': '55009580/50331096',
        'Spain': '54009550/50109552',
        'Turkey': '54009571/50331081'
    }
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    countries = {
        'UAE': '55009581/50331096',
        'UK': '54109556/50331064',
        'USA': '54009627/50331143'
    }
else:
    countries = {}

# Async function to fetch product IDs for a single category
async def get_json(page, store_id, cid):
    try:
        url = f'https://www.stradivarius.com/itxrest/3/catalog/store/{store_id}/category/{cid}/product?languageId=-1&showProducts=false&appId=1'
        await page.goto(url)
        content = await page.text_content("pre")
        json_data = json.loads(content)
        return json_data.get('productIds', [])
    except Exception as e:
        logging.error(f"Error processing category {cid}: {e}")
        return []

# Process one country using its own browser context/page
async def process_country(country, store_id, browser):
    logging.info(f"Starting country: {country}")
    p_dict = {}

    file_path = Path(f'{country}/Data/{today_str}/Item_urls/{country}_category_urls.json')
    if not file_path.exists():
        logging.error(f'Missing file: {file_path}')
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            subids = json.load(f)
    except Exception as e:
        logging.error(f"Error loading JSON for {country}: {e}")
        return

    context = await browser.new_context()
    page = await context.new_page()

    for gender in tqdm_asyncio(subids, desc=f"{country} Genders", ascii=(" ", "*")):
        p_dict[gender] = {}
        for category, c_dict in tqdm_asyncio(subids[gender].items(), desc=f"{gender}", leave=False, ascii=(" ", "*")):
            cid = c_dict.get("cid")
            product_ids = await get_json(page, store_id, cid)
            p_dict[gender][category] = product_ids

    await page.close()
    await context.close()

    # Save output
    try:
        output_path = Path(f'{country}/Data/{today_str}/Item_urls')
        output_path.mkdir(parents=True, exist_ok=True)
        out_file = output_path / f'{country}_product_ids.json'
        with open(out_file, "w", encoding='utf-8') as outfile:
            json.dump(p_dict, outfile, ensure_ascii=False, indent=4)
        logging.info(f"{country} product IDs saved to {out_file}")
    except Exception as e:
        logging.error(f"Error saving JSON for {country}: {e}")

# Main async entrypoint
async def main():
    if not countries:
        logging.info("No countries to process today.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        tasks = [
            process_country(country, store_id, browser)
            for country, store_id in countries.items()
        ]

        await asyncio.gather(*tasks)
        await browser.close()

# Run the script
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"Unexpected error in main execution: {e}")
